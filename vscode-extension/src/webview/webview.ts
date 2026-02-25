/**
 * 웹뷰 패널 관리자
 * - Finding 상세 정보를 웹뷰 패널로 표시
 */

import * as vscode from 'vscode';
import type { Finding } from '../api/types';
import { generateDetailHtml } from './panel-content';

export class WebviewManager {
  private panel: vscode.WebviewPanel | null = null;

  // 현재 표시 중인 finding (applyPatch 메시지 처리 시 참조)
  private currentFinding: Finding | null = null;

  /**
   * Finding 상세 정보 웹뷰 패널 표시
   */
  showDetail(finding: Finding, patchDiff?: string): void {
    this.currentFinding = finding;

    if (this.panel) {
      // 기존 패널이 있으면 재사용
      this.panel.reveal(vscode.ViewColumn.Beside);
    } else {
      // 새 패널 생성 (스크립트 활성화로 Apply Patch 버튼 동작)
      this.panel = vscode.window.createWebviewPanel(
        'vulnixDetail',
        `Vulnix: ${finding.rule_id}`,
        vscode.ViewColumn.Beside,
        {
          enableScripts: true,
          retainContextWhenHidden: false,
        }
      );

      // 패널이 닫힐 때 참조 해제
      this.panel.onDidDispose(() => {
        this.panel = null;
        this.currentFinding = null;
      });

      // 웹뷰에서 전송한 메시지 처리 (Apply Patch 버튼 클릭)
      this.panel.webview.onDidReceiveMessage((msg: { type: string }) => {
        if (msg.type === 'applyPatch' && this.currentFinding) {
          const targetFinding = this.currentFinding;
          void vscode.commands.executeCommand(
            'vulnix.applyPatch',
            vscode.Uri.file(targetFinding.file_path),
            targetFinding.rule_id
          );
        }
      });
    }

    this.panel.title = `Vulnix: ${finding.rule_id}`;
    this.panel.webview.html = generateDetailHtml(finding, patchDiff);
  }

  /**
   * 리소스 해제
   */
  dispose(): void {
    if (this.panel) {
      this.panel.dispose();
      this.panel = null;
    }
  }
}
