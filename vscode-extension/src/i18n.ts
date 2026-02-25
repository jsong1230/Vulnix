/**
 * 런타임 메시지 국제화 모듈
 * - VS Code 환경 언어(vscode.env.language)를 감지하여 한국어/영어 메시지를 반환
 * - package.nls.json / package.nls.ko.json 은 contributes 섹션(정적) 용
 * - 이 파일은 런타임 알림/UI 메시지 동적 번역에 사용
 */

import * as vscode from 'vscode';

/**
 * VS Code 현재 언어 감지 (env.language: 'ko', 'en', 'ja' 등)
 */
function getLocale(): 'ko' | 'en' {
  const lang = vscode.env.language;
  return lang.startsWith('ko') ? 'ko' : 'en';
}

const messages = {
  ko: {
    // 상태 표시줄
    statusAnalyzing: '$(loading~spin) Vulnix: 분석 중...',
    statusOffline: '$(shield) Vulnix: 오프라인',
    statusIssues: (n: number) => `$(shield) Vulnix: ${n}개 취약점`,
    statusOk: '$(shield) Vulnix: 취약점 없음',
    // 알림
    patchApplied: '패치가 성공적으로 적용되었습니다.',
    patchFailed: '패치 적용에 실패했습니다.',
    patchGenerating: '패치 생성 중...',
    analysisComplete: (n: number) => `분석 완료: ${n}개 취약점 발견`,
    authError: 'API Key가 유효하지 않습니다. 설정에서 확인해주세요.',
    rateLimitError: '요청 횟수 초과. 잠시 후 다시 시도해주세요.',
    serverError: '서버 오류가 발생했습니다.',
    fpSyncComplete: '오탐 패턴 동기화 완료',
    diagnosticsCleared: '진단이 초기화되었습니다.',
    notConfigured: 'API Key가 설정되지 않았습니다. 설정에서 vulnix.apiKey를 입력해주세요.',
    // 취약점 심각도
    severityCritical: '심각',
    severityHigh: '높음',
    severityMedium: '중간',
    severityLow: '낮음',
    // 상세 패널
    detailTitle: '취약점 상세',
    detailSeverity: '심각도',
    detailType: '취약점 유형',
    detailLocation: '위치',
    detailCwe: 'CWE',
    detailOwasp: 'OWASP',
    detailDescription: '설명',
    detailPatch: '패치 제안',
    applyPatchButton: '패치 적용',
  },
  en: {
    // Status bar
    statusAnalyzing: '$(loading~spin) Vulnix: analyzing...',
    statusOffline: '$(shield) Vulnix: offline',
    statusIssues: (n: number) => `$(shield) Vulnix: ${n} issue(s)`,
    statusOk: '$(shield) Vulnix: no issues',
    // Notifications
    patchApplied: 'Patch applied successfully.',
    patchFailed: 'Failed to apply patch.',
    patchGenerating: 'Generating patch...',
    analysisComplete: (n: number) => `Analysis complete: ${n} vulnerabilities found`,
    authError: 'Invalid API Key. Please check your settings.',
    rateLimitError: 'Rate limit exceeded. Please try again later.',
    serverError: 'Server error occurred.',
    fpSyncComplete: 'False positive patterns synced',
    diagnosticsCleared: 'Diagnostics cleared.',
    notConfigured: 'API Key not set. Please enter vulnix.apiKey in settings.',
    // Severity labels
    severityCritical: 'Critical',
    severityHigh: 'High',
    severityMedium: 'Medium',
    severityLow: 'Low',
    // Detail panel
    detailTitle: 'Vulnerability Detail',
    detailSeverity: 'Severity',
    detailType: 'Type',
    detailLocation: 'Location',
    detailCwe: 'CWE',
    detailOwasp: 'OWASP',
    detailDescription: 'Description',
    detailPatch: 'Patch Suggestion',
    applyPatchButton: 'Apply Patch',
  },
};

export type Messages = typeof messages.ko;

let _locale: 'ko' | 'en' | null = null;

/**
 * 현재 로케일에 맞는 메시지 객체 반환
 * - 최초 호출 시 vscode.env.language로 로케일 결정 후 캐싱
 */
export function t(): Messages {
  if (!_locale) {
    _locale = getLocale();
  }
  return messages[_locale];
}

/**
 * 캐싱된 로케일 초기화 (테스트용)
 */
export function resetLocale(): void {
  _locale = null;
}
