/**
 * 대시보드 관련 React Query 훅
 * F-04 설계서 5-1절 기준
 */
import { useQuery } from '@tanstack/react-query';
import { getDashboardSummary } from '@/lib/scan-api';

// ─── Query Keys ────────────────────────────────────────────────────────────────

export const dashboardKeys = {
  all: ['dashboard'] as const,
  summary: () => ['dashboard', 'summary'] as const,
};

// ─── 훅 ───────────────────────────────────────────────────────────────────────

/**
 * 대시보드 요약 통계 조회 훅
 * 서버에서 5분 TTL 캐시이므로 클라이언트 staleTime은 1분 설정
 */
export function useDashboardSummary() {
  return useQuery({
    queryKey: dashboardKeys.summary(),
    queryFn: getDashboardSummary,
    // staleTime: 1분 (설계서 8-3절 — 서버 Redis TTL 5분보다 짧게 설정)
    staleTime: 60 * 1000,
    // 창 포커스 시 재조회 (설계서 5-1절)
    refetchOnWindowFocus: true,
  });
}
