/**
 * 스캔 관련 React Query 훅
 * F-04 설계서 5-1절 기준
 */
import { useQuery } from '@tanstack/react-query';
import { getScan } from '@/lib/scan-api';

// ─── Query Keys ────────────────────────────────────────────────────────────────

export const scanKeys = {
  all: ['scans'] as const,
  detail: (id: string) => ['scans', id] as const,
};

// ─── 훅 ───────────────────────────────────────────────────────────────────────

/**
 * 스캔 상세 조회 훅
 * queued/running 상태이면 2초 간격으로 자동 폴링
 */
export function useScanDetail(scanId: string) {
  return useQuery({
    queryKey: scanKeys.detail(scanId),
    queryFn: () => getScan(scanId),
    // staleTime: 0 — 항상 최신 상태 확인 (설계서 8-3절)
    staleTime: 0,
    // 진행 중 상태이면 2초마다 폴링, 완료/실패이면 중단
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'queued' || status === 'running') {
        return 2000;
      }
      return false;
    },
  });
}
