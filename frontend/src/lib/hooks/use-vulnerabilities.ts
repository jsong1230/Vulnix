/**
 * 취약점 관련 React Query 훅
 * F-04 설계서 5-1절 기준
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getVulnerabilities,
  getVulnerability,
  patchVulnerabilityStatus,
  type VulnerabilityListParams,
  type VulnerabilityStatus,
} from '@/lib/scan-api';
import { dashboardKeys } from './use-dashboard';

// ─── Query Keys ────────────────────────────────────────────────────────────────

export const vulnerabilityKeys = {
  all: ['vulnerabilities'] as const,
  lists: () => ['vulnerabilities', 'list'] as const,
  list: (params: VulnerabilityListParams) =>
    ['vulnerabilities', 'list', params] as const,
  detail: (id: string) => ['vulnerabilities', id] as const,
};

// ─── 훅 ───────────────────────────────────────────────────────────────────────

/**
 * 취약점 목록 조회 훅
 * 페이지네이션 시 이전 데이터 유지 (깜빡임 방지)
 * params에 아무 값도 없고 enabled가 false이면 API 호출 생략
 */
export function useVulnerabilityList(
  params: VulnerabilityListParams = {},
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: vulnerabilityKeys.list(params),
    queryFn: () => getVulnerabilities(params),
    // staleTime: 30초 (설계서 8-3절)
    staleTime: 30 * 1000,
    // 페이지 이동 시 이전 데이터 유지 (keepPreviousData 대체: placeholderData)
    placeholderData: (previousData) => previousData,
    // enabled 옵션 — 외부에서 제어 가능
    enabled: options?.enabled ?? true,
  });
}

/**
 * 취약점 상세 조회 훅
 */
export function useVulnerabilityDetail(vulnId: string) {
  return useQuery({
    queryKey: vulnerabilityKeys.detail(vulnId),
    queryFn: () => getVulnerability(vulnId),
    // staleTime: 30초 (설계서 8-3절)
    staleTime: 30 * 1000,
  });
}

/**
 * 취약점 상태 변경 뮤테이션 훅
 * 성공 시 취약점 상세, 목록, 대시보드 쿼리 모두 무효화
 */
export function useUpdateVulnerabilityStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      vulnId,
      status,
      reason,
    }: {
      vulnId: string;
      status: VulnerabilityStatus;
      reason?: string;
    }) => patchVulnerabilityStatus(vulnId, status, reason),
    onSuccess: (_, { vulnId }) => {
      // 해당 취약점 상세 쿼리 무효화
      void queryClient.invalidateQueries({
        queryKey: vulnerabilityKeys.detail(vulnId),
      });
      // 취약점 목록 쿼리 전체 무효화
      void queryClient.invalidateQueries({
        queryKey: vulnerabilityKeys.lists(),
      });
      // 대시보드 요약 쿼리 무효화 (캐시 갱신)
      void queryClient.invalidateQueries({
        queryKey: dashboardKeys.summary(),
      });
    },
  });
}
