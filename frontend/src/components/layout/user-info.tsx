'use client';

import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';

interface UserMe {
  github_login: string;
  avatar_url: string | null;
}

/**
 * 로그인된 사용자 정보 표시 컴포넌트
 * GET /api/v1/auth/me 호출 후 아바타 + 로그인명 표시
 */
export function UserInfo({ loginLabel }: { loginLabel: string }) {
  const [user, setUser] = useState<UserMe | null>(null);

  useEffect(() => {
    apiClient
      .get<{ success: boolean; data?: UserMe }>('/api/v1/auth/me')
      .then((res) => {
        if (res.data.success && res.data.data) {
          setUser(res.data.data);
        }
      })
      .catch(() => {
        // 미인증 상태 — 로그인 링크 유지
      });
  }, []);

  if (!user) {
    return (
      <a
        href="/login"
        className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
      >
        {loginLabel}
      </a>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {user.avatar_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={user.avatar_url}
          alt={user.github_login}
          className="w-7 h-7 rounded-full"
        />
      ) : (
        <div className="w-7 h-7 bg-gray-700 rounded-full flex items-center justify-center">
          <span className="text-xs text-gray-400">
            {user.github_login[0].toUpperCase()}
          </span>
        </div>
      )}
      <span className="text-gray-300 text-sm">{user.github_login}</span>
    </div>
  );
}
