/**
 * Vulnix 설정 관리
 * - vscode workspace 설정에서 Vulnix 관련 설정을 읽어옴
 */

import * as vscode from 'vscode';

export class VulnixConfig {
  private get config(): vscode.WorkspaceConfiguration {
    return vscode.workspace.getConfiguration('vulnix');
  }

  /**
   * 서버 URL 반환
   * 기본값: https://api.vulnix.dev
   */
  getServerUrl(): string {
    return this.config.get<string>('serverUrl', 'https://api.vulnix.dev');
  }

  /**
   * API 키 반환
   * 기본값: ''
   */
  getApiKey(): string {
    return this.config.get<string>('apiKey', '');
  }

  /**
   * 설정 완료 여부 확인
   * apiKey와 serverUrl이 모두 비어있지 않으면 true
   */
  isConfigured(): boolean {
    const apiKey = this.getApiKey();
    const serverUrl = this.getServerUrl();
    return Boolean(apiKey) && Boolean(serverUrl);
  }

  /**
   * 심각도 필터 반환
   * 기본값: 'all'
   */
  getSeverityFilter(): 'all' | 'high' | 'critical' {
    return this.config.get<'all' | 'high' | 'critical'>('severityFilter', 'all');
  }

  /**
   * 저장 시 자동 분석 여부 반환
   * 기본값: true
   */
  isAnalyzeOnSaveEnabled(): boolean {
    return this.config.get<boolean>('analyzeOnSave', true);
  }

  /**
   * @deprecated isAnalyzeOnSaveEnabled() 사용 권장
   */
  isAnalyzeOnSave(): boolean {
    return this.isAnalyzeOnSaveEnabled();
  }
}
