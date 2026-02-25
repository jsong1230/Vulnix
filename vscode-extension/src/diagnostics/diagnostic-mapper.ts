/**
 * Finding → vscode.Diagnostic 변환 매퍼
 * - API Finding 객체를 VS Code 진단 객체로 변환
 * - 심각도 매핑, 라인 번호 0-base 변환, 메시지 포맷 처리
 */

import * as vscode from 'vscode';
import type { Finding } from '../api/types';

/**
 * Finding 심각도를 vscode.DiagnosticSeverity로 변환
 */
function mapSeverity(severity: Finding['severity']): vscode.DiagnosticSeverity {
  switch (severity) {
    case 'critical':
    case 'high':
      return vscode.DiagnosticSeverity.Error;
    case 'medium':
      return vscode.DiagnosticSeverity.Warning;
    case 'low':
      return vscode.DiagnosticSeverity.Information;
    case 'informational':
      return vscode.DiagnosticSeverity.Hint;
    default:
      return vscode.DiagnosticSeverity.Information;
  }
}

/**
 * CWE ID에서 숫자 추출하여 CWE URL 생성
 * 예: 'CWE-89' → 'https://cwe.mitre.org/data/definitions/89.html'
 */
function buildCweUri(cweId: string): vscode.Uri {
  const match = /CWE-(\d+)/i.exec(cweId);
  const cweNumber = match ? match[1] : cweId;
  return vscode.Uri.parse(`https://cwe.mitre.org/data/definitions/${cweNumber}.html`);
}

/**
 * Finding 객체를 vscode.Diagnostic으로 변환
 *
 * - 라인 번호: API 1-base → vscode 0-base 변환
 * - 메시지 형식: [Vulnix] {severity}: {message} ({cwe_id})
 * - source: 'Vulnix'
 * - code: { value: rule_id, target: CWE URL }
 */
export function mapFindingToDiagnostic(finding: Finding): vscode.Diagnostic {
  // 라인 번호 1-base → 0-base 변환
  const range = new vscode.Range(
    finding.start_line - 1,
    finding.start_col,
    finding.end_line - 1,
    finding.end_col
  );

  // 메시지 포맷: [Vulnix] {severity}: {message} ({cwe_id})
  const cweText = finding.cwe_id ? ` (${finding.cwe_id})` : '';
  const message = `[Vulnix] ${finding.severity}: ${finding.message}${cweText}`;

  const severity = mapSeverity(finding.severity);
  const diagnostic = new vscode.Diagnostic(range, message, severity);

  // source 설정
  diagnostic.source = 'Vulnix';

  // code 설정: { value: rule_id, target: CWE URL }
  if (finding.cwe_id) {
    diagnostic.code = {
      value: finding.rule_id,
      target: buildCweUri(finding.cwe_id),
    };
  } else {
    diagnostic.code = finding.rule_id;
  }

  // DiagnosticTag 설정: low 심각도에 Unnecessary 태그
  if (finding.severity === 'low' || finding.severity === 'informational') {
    diagnostic.tags = [vscode.DiagnosticTag.Unnecessary];
  }

  return diagnostic;
}
