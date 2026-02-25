/**
 * 오탐 패턴 관련 React Query 훅
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getFalsePositives,
  createFalsePositive,
  updateFalsePositive,
  deleteFalsePositive,
  type CreateFalsePositiveRequest,
  type UpdateFalsePositiveRequest,
} from '@/lib/false-positives-api';

// ─── Query Keys ────────────────────────────────────────────────────────────────

export const falsePositiveKeys = {
  all: ['falsePositives'] as const,
  lists: () => ['falsePositives', 'list'] as const,
};

// ─── 훅 ───────────────────────────────────────────────────────────────────────

/**
 * 오탐 패턴 목록 조회 훅
 */
export function useFalsePositives() {
  return useQuery({
    queryKey: falsePositiveKeys.lists(),
    queryFn: getFalsePositives,
    staleTime: 30 * 1000,
  });
}

/**
 * 오탐 패턴 등록 뮤테이션 훅
 */
export function useCreateFalsePositive() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateFalsePositiveRequest) => createFalsePositive(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: falsePositiveKeys.lists(),
      });
    },
  });
}

/**
 * 오탐 패턴 수정 뮤테이션 훅 (활성화/비활성화)
 */
export function useUpdateFalsePositive() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: UpdateFalsePositiveRequest;
    }) => updateFalsePositive(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: falsePositiveKeys.lists(),
      });
    },
  });
}

/**
 * 오탐 패턴 삭제 뮤테이션 훅
 */
export function useDeleteFalsePositive() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteFalsePositive(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: falsePositiveKeys.lists(),
      });
    },
  });
}
