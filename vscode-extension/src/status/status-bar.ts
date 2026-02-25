/**
 * 상태 표시줄 관리자
 * - VS Code 하단 상태 표시줄에 Vulnix 상태 표시
 */

import * as vscode from 'vscode';

export class StatusBarManager {
  private readonly item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.item.show();
  }

  /**
   * 연결됨 상태: 발견된 이슈 개수 표시
   */
  setConnected(issueCount: number): void {
    this.item.text = `$(shield) Vulnix: ${issueCount} issue(s)`;
  }

  /**
   * 오프라인 상태 표시
   */
  setOffline(): void {
    this.item.text = '$(shield) Vulnix: offline';
  }

  /**
   * 분석 중 상태 표시
   */
  setAnalyzing(): void {
    this.item.text = '$(loading~spin) Vulnix: analyzing...';
  }

  /**
   * 리소스 해제
   */
  dispose(): void {
    this.item.dispose();
  }
}
