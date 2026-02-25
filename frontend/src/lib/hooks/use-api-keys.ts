/**
 * IDE API Key 관련 React Query 훅
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getApiKeys,
  createApiKey,
  revokeApiKey,
  type CreateApiKeyRequest,
} from '@/lib/api-keys-api';

// ─── Query Keys ────────────────────────────────────────────────────────────────

export const apiKeyQueryKeys = {
  all: ['apiKeys'] as const,
  lists: () => ['apiKeys', 'list'] as const,
};

// ─── 훅 ───────────────────────────────────────────────────────────────────────

/**
 * API Key 목록 조회 훅
 */
export function useApiKeys() {
  return useQuery({
    queryKey: apiKeyQueryKeys.lists(),
    queryFn: getApiKeys,
    staleTime: 60 * 1000,
  });
}

/**
 * API Key 발급 뮤테이션 훅
 * 성공 시 목록 쿼리 무효화
 */
export function useCreateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateApiKeyRequest) => createApiKey(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: apiKeyQueryKeys.lists(),
      });
    },
  });
}

/**
 * API Key 비활성화 뮤테이션 훅
 */
export function useRevokeApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => revokeApiKey(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: apiKeyQueryKeys.lists(),
      });
    },
  });
}
