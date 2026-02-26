import axios, { type AxiosInstance, type AxiosError } from 'axios';

/**
 * 백엔드 API 응답 공통 형식
 * 시스템 설계 3-1절 기준
 */
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  meta?: {
    page: number;
    per_page: number;
    total: number;
  };
}

/**
 * 커스텀 API 에러 클래스
 * HTTP 상태 코드와 서버 에러 메시지를 포함
 */
export class ApiError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
    public readonly response?: ApiResponse,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * axios 인스턴스 생성
 * NEXT_PUBLIC_API_URL 환경변수 기반 baseURL 설정
 *
 * [CRITICAL-SEC-01 수정] localStorage 토큰 읽기 제거
 * HttpOnly 쿠키 방식으로 전환 → 브라우저가 쿠키를 자동으로 전송
 * withCredentials: true 설정으로 크로스 오리진 요청에도 쿠키 포함
 */
const createApiClient = (): AxiosInstance => {
  const instance = axios.create({
    // 상대 경로 사용 → Next.js rewrites가 /api/v1/* 를 Railway로 프록시
    // (직접 크로스 오리진 호출 시 HttpOnly 쿠키가 Railway 도메인으로 전송 불가)
    baseURL: '',
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: 30000, // 30초 타임아웃
    // 동일 오리진 요청에 쿠키 포함 (Next.js 프록시 경유)
    withCredentials: true,
  });

  // 요청 인터셉터 — 공통 요청 처리
  // HttpOnly 쿠키 방식에서는 브라우저가 쿠키를 자동으로 Authorization 헤더 대신 Cookie 헤더로 전송
  // 백엔드에서 Cookie 헤더의 access_token을 읽어 인증 처리해야 함
  instance.interceptors.request.use(
    (config) => config,
    (error: unknown) => Promise.reject(error),
  );

  // 응답 인터셉터 — 공통 에러 처리
  instance.interceptors.response.use(
    (response) => response,
    (error: AxiosError<ApiResponse>) => {
      const statusCode = error.response?.status ?? 0;
      const serverMessage =
        error.response?.data?.error ?? error.message ?? '알 수 없는 오류';

      // 401: 인증 만료 → 로그인 페이지로 리다이렉트
      // HttpOnly 쿠키 방식에서는 clear-token API Route를 통해 쿠키 삭제
      if (statusCode === 401 && typeof window !== 'undefined') {
        // 비동기 쿠키 삭제 후 리다이렉트 (fire-and-forget)
        fetch('/api/auth/clear-token', {
          method: 'POST',
          credentials: 'include',
        }).finally(() => {
          window.location.href = '/login';
        });
        return Promise.reject(new ApiError(401, '인증이 만료되었습니다.'));
      }

      // 403: 권한 없음
      if (statusCode === 403) {
        return Promise.reject(
          new ApiError(403, '이 작업을 수행할 권한이 없습니다.'),
        );
      }

      // 그 외 서버 에러
      return Promise.reject(
        new ApiError(statusCode, serverMessage, error.response?.data),
      );
    },
  );

  return instance;
};

/**
 * 싱글톤 API 클라이언트 인스턴스
 */
export const apiClient = createApiClient();

// 편의 메서드: API 응답에서 data 추출 헬퍼
export async function fetchApi<T>(
  url: string,
  options?: Parameters<typeof apiClient.get>[1],
): Promise<T> {
  const response = await apiClient.get<ApiResponse<T>>(url, options);
  if (!response.data.success || response.data.data === undefined) {
    throw new ApiError(
      response.status,
      response.data.error ?? '데이터를 가져오지 못했습니다.',
    );
  }
  return response.data.data;
}
