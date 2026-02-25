'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

interface QueryProviderProps {
  children: React.ReactNode;
}

/**
 * React Query 전역 공급자 컴포넌트
 * QueryClient 인스턴스를 앱 전체에 공급
 */
export function QueryProvider({ children }: QueryProviderProps) {
  // 컴포넌트 마운트 시 단 한 번 QueryClient 생성 (SSR 안전)
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // 기본 stale 시간: 30초
            staleTime: 30 * 1000,
            // 에러 시 재시도 1회
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
