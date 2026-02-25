/**
 * config.test.ts
 * - VulnixConfig 클래스 단위 테스트
 * - 설계서 섹션 5-2: VS Code 설정 (vulnix.serverUrl, vulnix.apiKey 등) 검증
 *
 * 인수조건 F-11:
 *   - VS Code 익스텐션으로 설치 가능
 *   - Vulnix 서버 연동하여 팀 오탐 규칙 동기화
 */

import { VulnixConfig } from '../../src/config';
import { workspace } from 'vscode';

// workspace.getConfiguration mock 참조
const mockGetConfiguration = workspace.getConfiguration as jest.Mock;

describe('VulnixConfig', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('isConfigured()', () => {
    it('apiKey가 빈 문자열이면 false를 반환한다', () => {
      // Arrange: apiKey 없음
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          const values: Record<string, unknown> = {
            serverUrl: 'https://api.vulnix.dev',
            apiKey: '', // 빈 문자열
            analyzeOnSave: true,
            severityFilter: 'all',
          };
          return values[key];
        },
      });

      const config = new VulnixConfig();

      // Act
      const result = config.isConfigured();

      // Assert
      expect(result).toBe(false);
    });

    it('apiKey가 undefined이면 false를 반환한다', () => {
      // Arrange
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          const values: Record<string, unknown> = {
            serverUrl: 'https://api.vulnix.dev',
            apiKey: undefined,
            analyzeOnSave: true,
            severityFilter: 'all',
          };
          return values[key];
        },
      });

      const config = new VulnixConfig();

      // Act
      const result = config.isConfigured();

      // Assert
      expect(result).toBe(false);
    });

    it('apiKey와 serverUrl이 모두 설정되면 true를 반환한다', () => {
      // Arrange: 유효한 설정
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          const values: Record<string, unknown> = {
            serverUrl: 'https://api.vulnix.dev',
            apiKey: 'vx_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6',
            analyzeOnSave: true,
            severityFilter: 'all',
          };
          return values[key];
        },
      });

      const config = new VulnixConfig();

      // Act
      const result = config.isConfigured();

      // Assert
      expect(result).toBe(true);
    });

    it('serverUrl이 빈 문자열이면 false를 반환한다', () => {
      // Arrange
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          const values: Record<string, unknown> = {
            serverUrl: '', // 빈 문자열
            apiKey: 'vx_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6',
            analyzeOnSave: true,
            severityFilter: 'all',
          };
          return values[key];
        },
      });

      const config = new VulnixConfig();

      // Act
      const result = config.isConfigured();

      // Assert
      expect(result).toBe(false);
    });
  });

  describe('severity 필터 기본값', () => {
    it('severityFilter 기본값은 "all"이다', () => {
      // Arrange: 기본값만 설정
      mockGetConfiguration.mockReturnValue({
        get: (key: string, defaultValue?: unknown) => {
          // severityFilter는 명시적 값 없음, 기본값 반환
          if (key === 'severityFilter') return defaultValue ?? 'all';
          const values: Record<string, unknown> = {
            serverUrl: 'https://api.vulnix.dev',
            apiKey: 'vx_live_testkey',
            analyzeOnSave: true,
          };
          return values[key];
        },
      });

      const config = new VulnixConfig();

      // Act
      const severityFilter = config.getSeverityFilter();

      // Assert
      expect(severityFilter).toBe('all');
    });

    it('"high"으로 설정된 severityFilter를 올바르게 반환한다', () => {
      // Arrange
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          const values: Record<string, unknown> = {
            serverUrl: 'https://api.vulnix.dev',
            apiKey: 'vx_live_testkey',
            analyzeOnSave: true,
            severityFilter: 'high',
          };
          return values[key];
        },
      });

      const config = new VulnixConfig();

      // Act
      const severityFilter = config.getSeverityFilter();

      // Assert
      expect(severityFilter).toBe('high');
    });

    it('"critical"으로 설정된 severityFilter를 올바르게 반환한다', () => {
      // Arrange
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          const values: Record<string, unknown> = {
            serverUrl: 'https://api.vulnix.dev',
            apiKey: 'vx_live_testkey',
            analyzeOnSave: false,
            severityFilter: 'critical',
          };
          return values[key];
        },
      });

      const config = new VulnixConfig();

      // Act
      const severityFilter = config.getSeverityFilter();

      // Assert
      expect(severityFilter).toBe('critical');
    });
  });

  describe('getServerUrl()', () => {
    it('설정된 serverUrl을 반환한다', () => {
      // Arrange
      const expectedUrl = 'https://custom.vulnix.dev';
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          if (key === 'serverUrl') return expectedUrl;
          return undefined;
        },
      });

      const config = new VulnixConfig();

      // Act
      const serverUrl = config.getServerUrl();

      // Assert
      expect(serverUrl).toBe(expectedUrl);
    });

    it('serverUrl이 설정되지 않으면 기본값 "https://api.vulnix.dev"를 반환한다', () => {
      // Arrange
      mockGetConfiguration.mockReturnValue({
        get: (key: string, defaultValue?: unknown) => {
          if (key === 'serverUrl') return defaultValue ?? 'https://api.vulnix.dev';
          return undefined;
        },
      });

      const config = new VulnixConfig();

      // Act
      const serverUrl = config.getServerUrl();

      // Assert
      expect(serverUrl).toBe('https://api.vulnix.dev');
    });
  });

  describe('getApiKey()', () => {
    it('설정된 apiKey를 반환한다', () => {
      // Arrange
      const expectedKey = 'vx_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6';
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          if (key === 'apiKey') return expectedKey;
          return undefined;
        },
      });

      const config = new VulnixConfig();

      // Act
      const apiKey = config.getApiKey();

      // Assert
      expect(apiKey).toBe(expectedKey);
    });
  });

  describe('analyzeOnSave 설정', () => {
    it('analyzeOnSave 기본값은 true이다', () => {
      // Arrange
      mockGetConfiguration.mockReturnValue({
        get: (key: string, defaultValue?: unknown) => {
          if (key === 'analyzeOnSave') return defaultValue ?? true;
          return undefined;
        },
      });

      const config = new VulnixConfig();

      // Act
      const analyzeOnSave = config.isAnalyzeOnSaveEnabled();

      // Assert
      expect(analyzeOnSave).toBe(true);
    });

    it('analyzeOnSave가 false로 설정되면 false를 반환한다', () => {
      // Arrange
      mockGetConfiguration.mockReturnValue({
        get: (key: string) => {
          if (key === 'analyzeOnSave') return false;
          return undefined;
        },
      });

      const config = new VulnixConfig();

      // Act
      const analyzeOnSave = config.isAnalyzeOnSaveEnabled();

      // Assert
      expect(analyzeOnSave).toBe(false);
    });
  });
});
