/**
 * API 클라이언트
 * - Vulnix 서버와 통신하는 HTTP 클라이언트
 * - 인증 에러, 레이트 리밋, 서버 에러 처리
 */

import type {
  AnalyzeRequest,
  Finding,
  FalsePositivePattern,
  PatchSuggestionRequest,
  PatchSuggestionResponse,
  AnalyzeResponse,
  FalsePositivePatternsResponse,
} from './types';

// 커스텀 에러 클래스 정의
export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthError';
  }
}

export class ServerError extends Error {
  public readonly statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.name = 'ServerError';
    this.statusCode = statusCode;
  }
}

export class RateLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RateLimitError';
  }
}

// analyze() 결과 타입
export interface AnalyzeResult {
  findings: Finding[];
  analysis_duration_ms: number;
  semgrep_version: string;
}

// getFalsePositivePatterns() 결과 타입
export interface FalsePositivePatternsResult {
  patterns: FalsePositivePattern[];
  etag: string;
  notModified: boolean;
}

export class ApiClient {
  private readonly serverUrl: string;
  private readonly apiKey: string;

  constructor(serverUrl: string, apiKey: string) {
    this.serverUrl = serverUrl;
    this.apiKey = apiKey;
  }

  /**
   * 파일 분석 요청
   * POST /api/v1/ide/analyze
   */
  async analyze(request: AnalyzeRequest): Promise<AnalyzeResult> {
    const url = `${this.serverUrl}/api/v1/ide/analyze`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const body = (await response.json()) as AnalyzeResponse;
      const errorCode = body.error?.code ?? 'UNKNOWN_ERROR';
      const errorMessage = body.error?.message ?? 'Unknown error';

      if (response.status === 401) {
        throw new AuthError(`${errorCode}: ${errorMessage}`);
      }

      if (response.status === 429) {
        throw new RateLimitError(`${errorCode}: ${errorMessage}`);
      }

      if (response.status >= 500) {
        throw new ServerError(`${errorCode}: ${errorMessage}`, response.status);
      }

      throw new ServerError(`${errorCode}: ${errorMessage}`, response.status);
    }

    const body = (await response.json()) as AnalyzeResponse;

    return {
      findings: body.data?.findings ?? [],
      analysis_duration_ms: body.data?.analysis_duration_ms ?? 0,
      semgrep_version: body.data?.semgrep_version ?? '',
    };
  }

  /**
   * 오탐 패턴 목록 조회
   * GET /api/v1/ide/false-positive-patterns
   */
  async getFalsePositivePatterns(etag?: string): Promise<FalsePositivePatternsResult> {
    const url = `${this.serverUrl}/api/v1/ide/false-positive-patterns`;

    const headers: Record<string, string> = {
      'X-API-Key': this.apiKey,
    };

    if (etag) {
      headers['If-None-Match'] = etag;
    }

    const response = await fetch(url, {
      method: 'GET',
      headers,
    });

    // 304 Not Modified: 변경 없음
    if (response.status === 304) {
      return {
        patterns: [],
        etag: etag ?? '',
        notModified: true,
      };
    }

    if (!response.ok) {
      const body = (await response.json()) as FalsePositivePatternsResponse;
      const errorCode = body.error?.code ?? 'UNKNOWN_ERROR';
      const errorMessage = body.error?.message ?? 'Unknown error';

      if (response.status === 401) {
        throw new AuthError(`${errorCode}: ${errorMessage}`);
      }

      if (response.status === 429) {
        throw new RateLimitError(`${errorCode}: ${errorMessage}`);
      }

      throw new ServerError(`${errorCode}: ${errorMessage}`, response.status);
    }

    const body = (await response.json()) as FalsePositivePatternsResponse;
    const responseEtag = response.headers.get('ETag') ?? '';

    return {
      patterns: body.data?.patterns ?? [],
      etag: responseEtag,
      notModified: false,
    };
  }

  /**
   * 패치 제안 요청
   * POST /api/v1/ide/patch-suggestion
   */
  async getPatchSuggestion(request: PatchSuggestionRequest): Promise<PatchSuggestionResponse> {
    const url = `${this.serverUrl}/api/v1/ide/patch-suggestion`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const body = (await response.json()) as PatchSuggestionResponse;
      const errorCode = body.error?.code ?? 'UNKNOWN_ERROR';
      const errorMessage = body.error?.message ?? 'Unknown error';

      if (response.status === 401) {
        throw new AuthError(`${errorCode}: ${errorMessage}`);
      }

      if (response.status === 429) {
        throw new RateLimitError(`${errorCode}: ${errorMessage}`);
      }

      throw new ServerError(`${errorCode}: ${errorMessage}`, response.status);
    }

    return (await response.json()) as PatchSuggestionResponse;
  }
}
