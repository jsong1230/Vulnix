/**
 * api-client.test.ts
 * - ApiClient 클래스 단위 테스트
 * - 설계서 섹션 5-3: HTTP 클라이언트 (api/client.ts) 검증
 * - 인증(X-API-Key 헤더), 성공/에러 응답 처리 검증
 *
 * 인수조건 F-11:
 *   - 코드 작성 중 실시간 취약점 하이라이팅 (API 통신)
 */

import { ApiClient, AuthError, ServerError, RateLimitError } from '../../src/api/client';
import apiResponses from '../fixtures/api-responses.json';

// fetch 전역 모킹
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('ApiClient', () => {
  let client: ApiClient;
  const SERVER_URL = 'https://api.vulnix.dev';
  const API_KEY = 'vx_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6';

  beforeEach(() => {
    jest.clearAllMocks();
    client = new ApiClient(SERVER_URL, API_KEY);
  });

  describe('analyze() 성공 케이스', () => {
    it('200 응답 시 findings 배열을 반환한다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => apiResponses.analyze_success,
      });

      const request = {
        file_path: 'src/api/routes/users.py',
        language: 'python',
        content: 'db.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        context: {
          workspace_name: 'my-project',
          git_branch: 'feature/login',
        },
      };

      // Act
      const result = await client.analyze(request);

      // Assert
      expect(result.findings).toBeDefined();
      expect(result.findings.length).toBeGreaterThan(0);
      expect(result.findings[0].rule_id).toBe('python.sqlalchemy.security.sql-injection');
    });

    it('findings가 없는 200 응답 시 빈 배열을 반환한다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => apiResponses.analyze_empty,
      });

      // Act
      const result = await client.analyze({
        file_path: 'src/safe.py',
        language: 'python',
        content: '# safe code',
        context: {},
      });

      // Assert
      expect(result.findings).toEqual([]);
    });
  });

  describe('analyze() 인증 실패 케이스', () => {
    it('401 응답 시 AuthError를 던진다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => apiResponses.auth_error_401,
      });

      // Act & Assert
      await expect(
        client.analyze({
          file_path: 'src/api/routes/users.py',
          language: 'python',
          content: 'some code',
          context: {},
        })
      ).rejects.toThrow(AuthError);
    });

    it('401 AuthError의 메시지에 인증 실패 정보가 포함된다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => apiResponses.auth_error_401,
      });

      // Act & Assert
      await expect(
        client.analyze({
          file_path: 'src/api/routes/users.py',
          language: 'python',
          content: 'some code',
          context: {},
        })
      ).rejects.toThrow(AuthError);

      try {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => apiResponses.auth_error_401,
        });
        await client.analyze({
          file_path: 'src/api/routes/users.py',
          language: 'python',
          content: 'some code',
          context: {},
        });
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).message).toContain('INVALID_API_KEY');
      }
    });
  });

  describe('analyze() 서버 오류 케이스', () => {
    it('500 응답 시 ServerError를 던진다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => apiResponses.server_error_500,
      });

      // Act & Assert
      await expect(
        client.analyze({
          file_path: 'src/api/routes/users.py',
          language: 'python',
          content: 'some code',
          context: {},
        })
      ).rejects.toThrow(ServerError);
    });

    it('500 ServerError의 메시지에 서버 오류 정보가 포함된다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => apiResponses.server_error_500,
      });

      // Act
      try {
        await client.analyze({
          file_path: 'src/api/routes/users.py',
          language: 'python',
          content: 'some code',
          context: {},
        });
      } catch (error) {
        // Assert
        expect(error).toBeInstanceOf(ServerError);
        expect((error as ServerError).statusCode).toBe(500);
      }
    });
  });

  describe('analyze() Rate Limit 케이스', () => {
    it('429 응답 시 RateLimitError를 던진다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => apiResponses.rate_limit_error_429,
      });

      // Act & Assert
      await expect(
        client.analyze({
          file_path: 'src/api/routes/users.py',
          language: 'python',
          content: 'some code',
          context: {},
        })
      ).rejects.toThrow(RateLimitError);
    });
  });

  describe('X-API-Key 헤더 포함 확인', () => {
    it('analyze() 요청에 X-API-Key 헤더가 포함된다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => apiResponses.analyze_empty,
      });

      // Act
      await client.analyze({
        file_path: 'src/safe.py',
        language: 'python',
        content: '# safe code',
        context: {},
      });

      // Assert: fetch 호출 시 X-API-Key 헤더 포함 확인
      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(url).toContain('/api/v1/ide/analyze');
      const headers = options.headers as Record<string, string>;
      expect(headers['X-API-Key']).toBe(API_KEY);
    });

    it('Content-Type: application/json 헤더가 포함된다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => apiResponses.analyze_empty,
      });

      // Act
      await client.analyze({
        file_path: 'src/safe.py',
        language: 'python',
        content: '# safe code',
        context: {},
      });

      // Assert
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Record<string, string>;
      expect(headers['Content-Type']).toBe('application/json');
    });

    it('요청 메서드는 POST이다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => apiResponses.analyze_empty,
      });

      // Act
      await client.analyze({
        file_path: 'src/safe.py',
        language: 'python',
        content: '# safe code',
        context: {},
      });

      // Assert
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(options.method).toBe('POST');
    });
  });

  describe('getFalsePositivePatterns()', () => {
    it('200 응답 시 패턴 목록을 반환한다', async () => {
      // Arrange
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => apiResponses.false_positive_patterns,
        headers: {
          get: (name: string) => (name === 'ETag' ? '"abc123def456"' : null),
        },
      });

      // Act
      const result = await client.getFalsePositivePatterns();

      // Assert
      expect(result.patterns).toBeDefined();
      expect(result.patterns.length).toBeGreaterThan(0);
    });

    it('ETag를 If-None-Match 헤더로 전송한다', async () => {
      // Arrange
      const etag = '"abc123def456"';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => apiResponses.false_positive_patterns,
        headers: {
          get: (name: string) => (name === 'ETag' ? etag : null),
        },
      });

      // Act
      await client.getFalsePositivePatterns(etag);

      // Assert
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Record<string, string>;
      expect(headers['If-None-Match']).toBe(etag);
    });
  });
});
