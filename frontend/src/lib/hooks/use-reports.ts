/**
 * CISO 리포트 관련 React Query 훅
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getReports,
  generateReport,
  downloadReport,
  type GenerateReportRequest,
} from '@/lib/reports-api';

// ─── Query Keys ────────────────────────────────────────────────────────────────

export const reportKeys = {
  all: ['reports'] as const,
  lists: () => ['reports', 'list'] as const,
};

// ─── 훅 ───────────────────────────────────────────────────────────────────────

/**
 * 리포트 목록 조회 훅
 */
export function useReports() {
  return useQuery({
    queryKey: reportKeys.lists(),
    queryFn: getReports,
    staleTime: 30 * 1000,
  });
}

/**
 * 리포트 생성 뮤테이션 훅
 * 성공 시 목록 쿼리 무효화
 */
export function useGenerateReport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: GenerateReportRequest) => generateReport(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: reportKeys.lists(),
      });
    },
  });
}

/**
 * 리포트 다운로드 뮤테이션 훅
 * Blob을 받아 브라우저 다운로드 트리거
 */
export function useDownloadReport() {
  return useMutation({
    mutationFn: ({ id, filename }: { id: string; filename: string }) =>
      downloadReport(id).then((blob) => ({ blob, filename })),
    onSuccess: ({ blob, filename }) => {
      // 브라우저 다운로드 트리거
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },
  });
}
