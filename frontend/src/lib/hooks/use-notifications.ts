/**
 * 알림 설정 관련 React Query 훅
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getNotifications,
  createNotification,
  updateNotification,
  deleteNotification,
  testNotification,
  type CreateNotificationRequest,
  type UpdateNotificationRequest,
} from '@/lib/notifications-api';

// ─── Query Keys ────────────────────────────────────────────────────────────────

export const notificationKeys = {
  all: ['notifications'] as const,
  lists: () => ['notifications', 'list'] as const,
};

// ─── 훅 ───────────────────────────────────────────────────────────────────────

/**
 * 알림 설정 목록 조회 훅
 */
export function useNotifications() {
  return useQuery({
    queryKey: notificationKeys.lists(),
    queryFn: getNotifications,
    staleTime: 30 * 1000,
  });
}

/**
 * 알림 설정 등록 뮤테이션 훅
 */
export function useCreateNotification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateNotificationRequest) => createNotification(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: notificationKeys.lists(),
      });
    },
  });
}

/**
 * 알림 설정 수정 뮤테이션 훅 (활성화/비활성화)
 */
export function useUpdateNotification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateNotificationRequest }) =>
      updateNotification(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: notificationKeys.lists(),
      });
    },
  });
}

/**
 * 알림 설정 삭제 뮤테이션 훅
 */
export function useDeleteNotification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteNotification(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: notificationKeys.lists(),
      });
    },
  });
}

/**
 * 알림 테스트 발송 뮤테이션 훅
 */
export function useTestNotification() {
  return useMutation({
    mutationFn: (id: string) => testNotification(id),
  });
}
