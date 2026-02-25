/**
 * 상단 헤더 컴포넌트
 * 현재 페이지 컨텍스트 + 사용자 프로필 표시
 * TODO: 사용자 인증 상태 연동 (GET /api/v1/auth/me)
 */
export function Header() {
  // TODO: useQuery(() => apiClient.get('/api/v1/auth/me')) 로 교체
  const user = null as {
    githubLogin: string;
    avatarUrl: string;
  } | null;

  return (
    <header className="h-14 border-b border-gray-800 flex items-center justify-between px-6 shrink-0">
      {/* 왼쪽: 알림 또는 검색 (추후 확장) */}
      <div className="flex items-center gap-3">
        {/* TODO: 검색 기능 추가 */}
      </div>

      {/* 오른쪽: 사용자 프로필 */}
      <div className="flex items-center gap-3">
        {user ? (
          /* 로그인된 사용자 */
          <div className="flex items-center gap-2">
            {user.avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={user.avatarUrl}
                alt={user.githubLogin}
                className="w-7 h-7 rounded-full"
              />
            ) : (
              <div className="w-7 h-7 bg-gray-700 rounded-full flex items-center justify-center">
                <span className="text-xs text-gray-400">
                  {user.githubLogin[0].toUpperCase()}
                </span>
              </div>
            )}
            <span className="text-gray-300 text-sm">{user.githubLogin}</span>
          </div>
        ) : (
          /* 미로그인 상태 */
          <a
            href="/login"
            className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            로그인
          </a>
        )}
      </div>
    </header>
  );
}
