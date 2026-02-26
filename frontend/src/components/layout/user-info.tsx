'use client';

import { useEffect, useRef, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import { logout } from '@/lib/auth';

interface UserMe {
  github_login: string;
  avatar_url: string | null;
}

/**
 * 로그인된 사용자 정보 표시 컴포넌트
 * GET /api/v1/auth/me 호출 후 아바타 + 로그인명 + 로그아웃 드롭다운 표시
 */
export function UserInfo({ loginLabel }: { loginLabel: string }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

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

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setOpen(false);
    window.location.href = '/login';
  };

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
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-gray-800 transition-colors"
      >
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
        <svg className="w-3 h-3 text-gray-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-40 rounded-lg border border-gray-700 bg-gray-900 shadow-lg z-50">
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gray-300 hover:bg-gray-800 hover:text-white rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
            </svg>
            로그아웃
          </button>
        </div>
      )}
    </div>
  );
}
