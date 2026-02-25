/**
 * CISO 리포트 관련 API 클라이언트
 * 보안 리포트 생성/목록 조회/다운로드
 */
import { apiClient, type ApiResponse } from './api-client';

// ─── 타입 정의 ─────────────────────────────────────────────────────────────────

export type ReportType = 'CSAP' | 'ISO27001' | 'ISMS';
export type ReportStatus = 'pending' | 'completed' | 'failed';

/**
 * 리포트 항목
 * GET /api/v1/reports 응답 data[] 항목
 */
export interface Report {
  id: string;
  reportType: ReportType;
  status: ReportStatus;
  startDate: string;
  endDate: string;
  teamName: string | null;
  createdAt: string;
  completedAt: string | null;
}

/**
 * 리포트 생성 요청 바디
 * POST /api/v1/reports/generate
 */
export interface GenerateReportRequest {
  reportType: ReportType;
  startDate: string;
  endDate: string;
  teamName?: string;
}

// ─── 백엔드 Raw 타입 ────────────────────────────────────────────────────────────

interface RawReport {
  id: string;
  report_type: ReportType;
  status: ReportStatus;
  start_date: string;
  end_date: string;
  team_name: string | null;
  created_at: string;
  completed_at: string | null;
}

// ─── 변환 헬퍼 ─────────────────────────────────────────────────────────────────

function toReport(raw: RawReport): Report {
  return {
    id: raw.id,
    reportType: raw.report_type,
    status: raw.status,
    startDate: raw.start_date,
    endDate: raw.end_date,
    teamName: raw.team_name,
    createdAt: raw.created_at,
    completedAt: raw.completed_at,
  };
}

// ─── API 함수 ──────────────────────────────────────────────────────────────────

/**
 * 리포트 목록 조회
 * GET /api/v1/reports
 */
export async function getReports(): Promise<Report[]> {
  const response = await apiClient.get<ApiResponse<RawReport[]>>(
    '/api/v1/reports',
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '리포트 목록을 가져오지 못했습니다.');
  }
  return response.data.data.map(toReport);
}

/**
 * 리포트 생성
 * POST /api/v1/reports/generate
 */
export async function generateReport(
  data: GenerateReportRequest,
): Promise<Report> {
  const response = await apiClient.post<ApiResponse<RawReport>>(
    '/api/v1/reports/generate',
    {
      report_type: data.reportType,
      start_date: data.startDate,
      end_date: data.endDate,
      team_name: data.teamName ?? null,
    },
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '리포트 생성에 실패했습니다.');
  }
  return toReport(response.data.data);
}

/**
 * 리포트 다운로드 (Blob)
 * GET /api/v1/reports/{id}/download
 */
export async function downloadReport(id: string): Promise<Blob> {
  const response = await apiClient.get(`/api/v1/reports/${id}/download`, {
    responseType: 'blob',
  });
  return response.data as Blob;
}
