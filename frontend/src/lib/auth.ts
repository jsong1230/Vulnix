/**
 * GitHub OAuth 인증 유틸리티
 * 시스템 설계 3-7절 인증 흐름 기준:
 *   GitHub OAuth -> Backend에서 JWT 발급 -> HttpOnly 쿠키에 토큰 저장
 *
 * [CRITICAL-SEC-01 수정] localStorage → HttpOnly 쿠키 방식으로 전환
 * XSS 공격으로 토큰이 탈취되는 취약점 제거
 */

/**
 * GitHub OAuth 로그인 URL 생성
 * state 파라미터: CSRF 방지 (무작위 값)
 * TODO: NEXT_PUBLIC_GITHUB_CLIENT_ID 환경변수 추가 필요
 */
export function getGitHubOAuthUrl(): string {
  const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID ?? '';
  const redirectUri = `${process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'}/auth/callback`;

  // CSRF 방지를 위한 state 값 생성
  const state = generateOAuthState();

  // state를 세션스토리지에 임시 저장 (콜백에서 검증)
  if (typeof window !== 'undefined') {
    sessionStorage.setItem('oauth_state', state);
  }

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: 'read:user user:email repo',
    state,
  });

  return `https://github.com/login/oauth/authorize?${params.toString()}`;
}

/**
 * OAuth 콜백 처리
 * URL의 code + state 파라미터를 백엔드로 전송하여 JWT 발급
 * TODO: POST /api/v1/auth/github 연동
 */
export async function handleOAuthCallback(
  code: string,
  state: string,
): Promise<void> {
  // state 검증 (CSRF 방지)
  if (typeof window !== 'undefined') {
    const savedState = sessionStorage.getItem('oauth_state');
    if (savedState !== state) {
      throw new Error('OAuth state 검증 실패: CSRF 공격 가능성');
    }
    sessionStorage.removeItem('oauth_state');
  }

  // TODO: 백엔드에 code 전송하여 JWT 발급
  // const response = await apiClient.post<ApiResponse<{ access_token: string; refresh_token: string }>>(
  //   '/api/v1/auth/github',
  //   { code, state }
  // );
  // await saveTokens(response.data.data!.access_token, response.data.data!.refresh_token);
}

/**
 * JWT 토큰 저장 — HttpOnly 쿠키 방식
 * Next.js API Route(/api/auth/set-token)를 통해 서버에서 쿠키 설정
 * HttpOnly 쿠키는 JS에서 접근 불가 → XSS 취약점 제거
 */
export async function saveTokens(
  accessToken: string,
  refreshToken?: string,
): Promise<void> {
  const response = await fetch('/api/auth/set-token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      access_token: accessToken,
      refresh_token: refreshToken,
    }),
  });

  if (!response.ok) {
    throw new Error('토큰 저장에 실패했습니다.');
  }
}

/**
 * 로그아웃 — HttpOnly 쿠키 삭제
 * Next.js API Route(/api/auth/clear-token)를 통해 서버에서 쿠키 삭제
 * HttpOnly 쿠키는 클라이언트 JS로 직접 삭제 불가
 */
export async function logout(): Promise<void> {
  await fetch('/api/auth/clear-token', {
    method: 'POST',
    credentials: 'include',
  });
}

/**
 * 로그인 상태 확인
 * HttpOnly 쿠키 방식에서는 클라이언트 JS가 토큰을 직접 읽을 수 없음
 * 대신 API 호출 결과로 인증 상태를 판단하거나, 별도 세션 API를 사용해야 함
 * 현재는 쿠키 존재 여부를 document.cookie에서 확인 (non-HttpOnly 플래그 쿠키와 구분 필요)
 *
 * 참고: HttpOnly 쿠키는 JS에서 읽을 수 없으므로, 인증 상태는 서버에서 확인하는 것이 원칙
 * SSR/미들웨어 레벨에서 인증 여부를 판단하고 리다이렉트 처리 권장
 */
export function isAuthenticated(): boolean {
  // 서버 환경에서는 판단 불가
  if (typeof window === 'undefined') return false;
  // 클라이언트에서는 쿠키 직접 읽기 불가(HttpOnly) → 세션 상태를 별도 관리하거나 SSR에서 처리
  // 임시: window.__AUTH_STATE__ 등 서버가 hydration 시 주입한 값 활용 가능
  return false;
}

/**
 * CSRF 방지용 무작위 state 값 생성
 */
function generateOAuthState(): string {
  const array = new Uint8Array(16);
  if (typeof window !== 'undefined' && window.crypto) {
    window.crypto.getRandomValues(array);
  }
  return Array.from(array, (byte) => byte.toString(16).padStart(2, '0')).join('');
}
