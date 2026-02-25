/**
 * 웹뷰 패널 HTML 생성기
 * - Finding 상세 정보를 HTML로 렌더링
 * - XSS 방지를 위한 HTML 이스케이프 처리
 */

import type { Finding } from '../api/types';

/**
 * HTML 특수 문자 이스케이프 (XSS 방지)
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * 심각도에 따른 배지 색상 반환
 */
function getSeverityColor(severity: Finding['severity']): string {
  switch (severity) {
    case 'critical': return '#dc2626';
    case 'high': return '#ea580c';
    case 'medium': return '#d97706';
    case 'low': return '#2563eb';
    case 'informational': return '#6b7280';
    default: return '#6b7280';
  }
}

/**
 * Finding 상세 정보를 HTML로 생성
 *
 * @param finding Finding 객체
 * @param patchDiff 패치 diff (선택)
 * @returns HTML 문자열
 */
export function generateDetailHtml(finding: Finding, patchDiff?: string): string {
  const severityColor = getSeverityColor(finding.severity);
  const cweSection = finding.cwe_id
    ? `<p><strong>CWE:</strong> <a href="https://cwe.mitre.org/data/definitions/${escapeHtml(finding.cwe_id.replace('CWE-', ''))}.html">${escapeHtml(finding.cwe_id)}</a></p>`
    : '';

  const owaspSection = finding.owasp_category
    ? `<p><strong>OWASP:</strong> ${escapeHtml(finding.owasp_category)}</p>`
    : '';

  const patchSection = patchDiff
    ? `<h3>Patch Suggestion</h3><pre><code>${escapeHtml(patchDiff)}</code></pre>`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
  <title>Vulnix - Vulnerability Detail</title>
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 16px; }
    .severity-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; color: white; font-weight: bold; background-color: ${severityColor}; }
    pre { background: var(--vscode-textBlockQuote-background); padding: 12px; border-radius: 4px; overflow: auto; }
    code { font-family: var(--vscode-editor-font-family); }
    a { color: var(--vscode-textLink-foreground); }
    .apply-patch-btn {
      display: inline-block;
      margin-top: 12px;
      padding: 6px 16px;
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 2px;
      cursor: pointer;
      font-size: 13px;
    }
    .apply-patch-btn:hover { background-color: var(--vscode-button-hoverBackground); }
  </style>
</head>
<body>
  <h2>${escapeHtml(finding.rule_id)}</h2>
  <p><span class="severity-badge">${escapeHtml(finding.severity.toUpperCase())}</span></p>
  <p>${escapeHtml(finding.message)}</p>
  <p><strong>File:</strong> ${escapeHtml(finding.file_path)} (line ${finding.start_line})</p>
  ${cweSection}
  ${owaspSection}
  <h3>Code Snippet</h3>
  <pre><code>${escapeHtml(finding.code_snippet)}</code></pre>
  ${patchSection}
  <button class="apply-patch-btn" onclick="applyPatch()">Apply Patch</button>
  <script>
    const vscode = acquireVsCodeApi();
    function applyPatch() {
      vscode.postMessage({ type: 'applyPatch' });
    }
  </script>
</body>
</html>`;
}
