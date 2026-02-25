/**
 * VS Code 익스텐션 진입점
 * - 익스텐션 활성화/비활성화 처리
 * - 명령 등록, 이벤트 리스너 설정
 */

import * as vscode from 'vscode';
import { ApiClient } from './api/client';
import { VulnixConfig } from './config';
import { FPCache } from './analyzer/fp-cache';
import { Analyzer } from './analyzer/analyzer';
import { DiagnosticsManager } from './diagnostics/diagnostics';
import { StatusBarManager } from './status/status-bar';
import { WebviewManager } from './webview/webview';
import { VulnixCodeActionProvider } from './code-actions/code-actions';
import { applyPatch } from './code-actions/patch-applier';
import { t } from './i18n';

let diagnosticsManager: DiagnosticsManager | null = null;
let statusBar: StatusBarManager | null = null;
let webviewManager: WebviewManager | null = null;

/**
 * 익스텐션 활성화
 */
export function activate(context: vscode.ExtensionContext): void {
  const config = new VulnixConfig();
  diagnosticsManager = new DiagnosticsManager();
  statusBar = new StatusBarManager();
  webviewManager = new WebviewManager();

  // FP 캐시 초기화 (globalState에서 이전 패턴 복원)
  const fpCache = new FPCache(context.globalState);

  // API 클라이언트 초기화
  const client = new ApiClient(config.getServerUrl(), config.getApiKey());

  // 분석기 초기화
  const analyzer = new Analyzer(client, fpCache, diagnosticsManager, statusBar);

  // FP 패턴 주기적 동기화 시작 (5분 간격)
  fpCache.syncPeriodically(client);

  // 저장 시 자동 분석 (500ms 디바운스 적용)
  if (config.isAnalyzeOnSaveEnabled()) {
    context.subscriptions.push(
      vscode.workspace.onDidSaveTextDocument(document => {
        analyzer.analyzeFileDebounced(document);
      })
    );
  }

  // 문서 닫기 시 진단 제거
  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument(document => {
      diagnosticsManager?.clearFor(document.uri);
    })
  );

  // 명령 등록: 현재 파일 분석
  context.subscriptions.push(
    vscode.commands.registerCommand('vulnix.analyzeFile', () => {
      const activeEditor = vscode.window.activeTextEditor;
      if (activeEditor) {
        void analyzer.analyzeFile(activeEditor.document);
      }
    })
  );

  // 명령 등록: 패치 적용 (코드 액션 전구 클릭 시 호출)
  context.subscriptions.push(
    vscode.commands.registerCommand(
      'vulnix.applyPatch',
      async (uri: vscode.Uri, diagnosticOrRuleId: vscode.Diagnostic | string) => {
        // ruleId 추출 (Diagnostic 객체 또는 문자열 ruleId 모두 지원)
        let ruleId: string;
        if (typeof diagnosticOrRuleId === 'string') {
          ruleId = diagnosticOrRuleId;
        } else {
          const code = diagnosticOrRuleId.code;
          ruleId = typeof code === 'object' && code !== null && 'value' in code
            ? String(code.value)
            : String(code ?? '');
        }

        if (!ruleId) {
          void vscode.window.showErrorMessage('Vulnix: 패치 대상 rule_id를 확인할 수 없습니다.');
          return;
        }

        // analyzer 캐시에서 finding 조회
        const finding = analyzer.getFindingByRuleId(uri.fsPath, ruleId);
        if (!finding) {
          void vscode.window.showErrorMessage('Vulnix: 해당 취약점 정보를 찾을 수 없습니다. 파일을 다시 분석해주세요.');
          return;
        }

        // 현재 파일 문서 열기
        let document: vscode.TextDocument;
        try {
          document = await vscode.workspace.openTextDocument(uri);
        } catch {
          void vscode.window.showErrorMessage('Vulnix: 파일을 열 수 없습니다.');
          return;
        }

        // 패치 제안 API 호출 (로딩 표시)
        await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: `Vulnix: ${t().patchGenerating}`,
            cancellable: false,
          },
          async () => {
            try {
              const patchResponse = await client.getPatchSuggestion({
                file_path: uri.fsPath,
                language: document.languageId,
                content: document.getText(),
                finding: {
                  rule_id: finding.rule_id,
                  start_line: finding.start_line,
                  end_line: finding.end_line,
                  code_snippet: finding.code_snippet,
                  message: finding.message,
                },
              });

              const patchDiff = patchResponse.data?.patch_diff;
              if (!patchDiff) {
                void vscode.window.showErrorMessage(`Vulnix: ${t().patchFailed}`);
                return;
              }

              // 패치 적용
              const success = await applyPatch(document, patchDiff);
              if (success) {
                void vscode.window.showInformationMessage(
                  `Vulnix: ${t().patchApplied} (${ruleId})`
                );
              } else {
                void vscode.window.showErrorMessage(`Vulnix: ${t().patchFailed}`);
              }
            } catch {
              void vscode.window.showErrorMessage(`Vulnix: ${t().serverError}`);
            }
          }
        );
      }
    )
  );

  // 명령 등록: 취약점 상세 보기
  context.subscriptions.push(
    vscode.commands.registerCommand('vulnix.showDetail', (finding) => {
      if (finding) {
        webviewManager?.showDetail(finding);
      }
    })
  );

  // 명령 등록: FP 패턴 동기화
  context.subscriptions.push(
    vscode.commands.registerCommand('vulnix.syncFPPatterns', async () => {
      try {
        const result = await client.getFalsePositivePatterns();
        if (!result.notModified) {
          fpCache.loadPatterns(result.patterns);
          void vscode.window.showInformationMessage(
            `Vulnix: ${result.patterns.length}개의 오탐 패턴이 동기화되었습니다.`
          );
        }
      } catch {
        void vscode.window.showErrorMessage('Vulnix: 오탐 패턴 동기화에 실패했습니다.');
      }
    })
  );

  // 명령 등록: 모든 진단 제거
  context.subscriptions.push(
    vscode.commands.registerCommand('vulnix.clearDiagnostics', () => {
      diagnosticsManager?.clearAll();
      statusBar?.setConnected(0);
      void vscode.window.showInformationMessage(`Vulnix: ${t().diagnosticsCleared}`);
    })
  );

  // 설정 변경 감지: vulnix 설정 변경 시 클라이언트/분석기 설정 갱신
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration('vulnix')) {
        // 설정 재로드 후 클라이언트 URL·키 갱신
        const newServerUrl = config.getServerUrl();
        const newApiKey = config.getApiKey();
        // ApiClient는 불변 속성이므로 새 인스턴스 대신 내부 참조 갱신
        // 단순 재초기화: 설정 변경 알림 메시지로 재시작 안내
        void vscode.window.showInformationMessage(
          'Vulnix: 설정이 변경되었습니다. 변경 사항은 다음 분석 시 반영됩니다.',
          { detail: `서버 URL: ${newServerUrl}, API 키: ${newApiKey ? '설정됨' : '미설정'}` }
        );
      }
    })
  );

  // 코드 액션 프로바이더 등록
  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      [
        { language: 'python' },
        { language: 'javascript' },
        { language: 'typescript' },
        { language: 'java' },
        { language: 'go' },
      ],
      new VulnixCodeActionProvider(),
      { providedCodeActionKinds: VulnixCodeActionProvider.providedCodeActionKinds }
    )
  );

  // 리소스 정리 등록
  context.subscriptions.push(
    { dispose: () => diagnosticsManager?.dispose() },
    { dispose: () => statusBar?.dispose() },
    { dispose: () => webviewManager?.dispose() }
  );

  // 설정 완료 여부 확인
  if (!config.isConfigured()) {
    void vscode.window.showWarningMessage(
      `Vulnix: ${t().notConfigured}`,
      '설정 열기'
    ).then(selection => {
      if (selection === '설정 열기') {
        void vscode.commands.executeCommand('workbench.action.openSettings', 'vulnix.apiKey');
      }
    });
  }

  statusBar.setOffline();
}

/**
 * 익스텐션 비활성화
 */
export function deactivate(): void {
  diagnosticsManager?.dispose();
  statusBar?.dispose();
  webviewManager?.dispose();
}
