'use client';

import { useEffect } from 'react';

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    // 에러 로깅 (프로덕션에서는 Sentry 등으로 교체)
    console.error('[GlobalError]', error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-8 text-center">
      <div className="w-12 h-12 rounded-full bg-red-900/30 flex items-center justify-center mb-4">
        <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-white mb-2">페이지를 불러오는 중 오류가 발생했습니다</h2>
      <p className="text-gray-400 text-sm mb-6 max-w-sm">
        {error.message ?? '예기치 않은 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'}
      </p>
      <button
        type="button"
        onClick={reset}
        className="btn-primary"
      >
        다시 시도
      </button>
    </div>
  );
}
