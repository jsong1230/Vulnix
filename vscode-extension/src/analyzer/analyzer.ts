/**
 * 파일 분석기
 * - API를 통해 파일 보안 취약점 분석
 * - FP 캐시로 오탐 필터링
 * - 진단 및 상태 표시줄 업데이트
 */

import * as vscode from 'vscode';
import type { ApiClient } from '../api/client';
import type { FPCache } from './fp-cache';
import type { DiagnosticsManager } from '../diagnostics/diagnostics';
import type { StatusBarManager } from '../status/status-bar';
import type { Finding } from '../api/types';

// 지원 언어 목록
const SUPPORTED_LANGUAGES = ['python', 'javascript', 'typescript', 'java', 'go'];

// 파일 크기 제한 (1MB)
const MAX_FILE_SIZE = 1024 * 1024;

// 디바운스 지연 시간 (ms)
const DEBOUNCE_DELAY_MS = 500;

// 문서 타입 인터페이스 (테스트 가능하도록 추상화)
interface DocumentLike {
  uri: { fsPath: string };
  languageId: string;
  getText(): string;
}

export class Analyzer {
  private readonly client: ApiClient;
  private readonly fpCache: FPCache;
  private readonly diagnosticsManager: DiagnosticsManager;
  private readonly statusBar: StatusBarManager;

  // 파일별 분석 결과 캐시 (applyPatch 명령에서 참조)
  private findingsCache = new Map<string, Finding[]>();

  // 디바운스 타이머
  private debounceTimer: NodeJS.Timeout | null = null;

  constructor(
    client: ApiClient,
    fpCache: FPCache,
    diagnosticsManager: DiagnosticsManager,
    statusBar: StatusBarManager
  ) {
    this.client = client;
    this.fpCache = fpCache;
    this.diagnosticsManager = diagnosticsManager;
    this.statusBar = statusBar;
  }

  /**
   * 디바운스 적용된 파일 분석 (연속 저장 시 마지막 요청만 실행)
   * 500ms 이내 재호출 시 이전 타이머 취소
   */
  analyzeFileDebounced(document: DocumentLike): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    this.debounceTimer = setTimeout(() => {
      void this.analyzeFile(document);
    }, DEBOUNCE_DELAY_MS);
  }

  /**
   * 파일 분석 수행
   * - 지원 언어 확인
   * - 파일 크기 확인 (1MB 초과 스킵)
   * - API 호출 → findings → FP 필터 → diagnostics 업데이트
   */
  async analyzeFile(document: DocumentLike): Promise<void> {
    const { fsPath } = document.uri;
    const content = document.getText();

    // 지원 언어 확인
    if (!SUPPORTED_LANGUAGES.includes(document.languageId)) {
      return;
    }

    // 파일 크기 확인 (1MB 초과 스킵)
    if (Buffer.byteLength(content, 'utf8') > MAX_FILE_SIZE) {
      return;
    }

    this.statusBar.setAnalyzing();

    try {
      const result = await this.client.analyze({
        file_path: fsPath,
        language: document.languageId,
        content,
      });

      // FP 필터 적용
      const filteredFindings = result.findings.filter(
        finding => !this.fpCache.matchesAny({ rule_id: finding.rule_id, file_path: finding.file_path })
      );

      // findings 캐시 저장 (applyPatch 명령에서 참조)
      this.findingsCache.set(fsPath, filteredFindings);

      // 진단 업데이트
      const uri = vscode.Uri.file(fsPath);
      this.diagnosticsManager.update(uri, filteredFindings);
      this.statusBar.setConnected(filteredFindings.length);
    } catch {
      this.statusBar.setOffline();
    }
  }

  /**
   * 특정 파일에서 ruleId로 finding 조회
   * - applyPatch 명령에서 패치 대상 finding 조회 시 사용
   */
  getFindingByRuleId(filePath: string, ruleId: string): Finding | undefined {
    const findings = this.findingsCache.get(filePath);
    if (!findings) {
      return undefined;
    }
    return findings.find(f => f.rule_id === ruleId);
  }
}
