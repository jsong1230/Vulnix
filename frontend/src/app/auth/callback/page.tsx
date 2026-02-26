'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import { saveTokens } from '@/lib/auth';

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code) {
      setError('인증 코드가 없습니다.');
      return;
    }

    const savedState = sessionStorage.getItem('oauth_state');
    if (savedState && state && savedState !== state) {
      setError('보안 검증에 실패했습니다. 다시 시도해주세요.');
      return;
    }
    sessionStorage.removeItem('oauth_state');

    apiClient
      .post<{ success: boolean; data: { access_token: string; refresh_token: string } }>(
        '/api/v1/auth/github',
        { code, state },
      )
      .then(async (response) => {
        if (response.data.success && response.data.data) {
          await saveTokens(
            response.data.data.access_token,
            response.data.data.refresh_token,
          );
          router.replace('/dashboard');
        }
      })
      .catch(() => {
        setError('로그인에 실패했습니다. 다시 시도해주세요.');
      });
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <button
            onClick={() => router.replace('/')}
            className="text-blue-500 underline"
          >
            홈으로 돌아가기
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4" />
        <p className="text-gray-600">로그인 처리 중...</p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        </div>
      }
    >
      <CallbackHandler />
    </Suspense>
  );
}
