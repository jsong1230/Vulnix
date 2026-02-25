/**
 * 코드 액션 프로바이더
 * - Vulnix 진단에 대한 QuickFix 액션 제공
 */

import * as vscode from 'vscode';

export class VulnixCodeActionProvider implements vscode.CodeActionProvider {
  static readonly providedCodeActionKinds = [vscode.CodeActionKind.QuickFix];

  /**
   * 커서 위치의 Vulnix 진단에 대한 코드 액션 제공
   */
  provideCodeActions(
    document: vscode.TextDocument,
    range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext
  ): vscode.CodeAction[] {
    // Vulnix 소스의 진단만 처리
    const vulnixDiagnostics = context.diagnostics.filter(d => d.source === 'Vulnix');

    if (vulnixDiagnostics.length === 0) {
      return [];
    }

    const actions: vscode.CodeAction[] = [];

    for (const diagnostic of vulnixDiagnostics) {
      // 패치 제안 액션
      const fixAction = new vscode.CodeAction(
        `Vulnix: Apply patch for ${diagnostic.code?.toString() ?? 'vulnerability'}`,
        vscode.CodeActionKind.QuickFix
      );
      fixAction.command = {
        command: 'vulnix.applyPatch',
        title: 'Apply Vulnix Patch',
        arguments: [document.uri, diagnostic],
      };
      fixAction.diagnostics = [diagnostic];
      fixAction.isPreferred = true;

      // 상세 보기 액션
      const detailAction = new vscode.CodeAction(
        `Vulnix: Show detail for ${diagnostic.code?.toString() ?? 'vulnerability'}`,
        vscode.CodeActionKind.Empty
      );
      detailAction.command = {
        command: 'vulnix.showDetail',
        title: 'Show Vulnix Detail',
        arguments: [diagnostic],
      };

      actions.push(fixAction, detailAction);
    }

    return actions;
  }
}
