/**
 * 알림 설정 관련 API 클라이언트
 * Slack/Teams Webhook 설정 CRUD + 테스트 발송
 */
import { apiClient, type ApiResponse } from './api-client';

// ─── 타입 정의 ─────────────────────────────────────────────────────────────────

export type NotificationPlatform = 'slack' | 'teams';
export type SeverityThreshold = 'all' | 'high' | 'critical';

/**
 * 알림 설정 항목
 * GET /api/v1/notifications 응답 data[] 항목
 */
export interface NotificationConfig {
  id: string;
  platform: NotificationPlatform;
  webhookUrl: string;
  severityThreshold: SeverityThreshold;
  weeklyReportEnabled: boolean;
  isActive: boolean;
  createdAt: string;
}

/**
 * 알림 설정 등록 요청 바디
 * POST /api/v1/notifications
 */
export interface CreateNotificationRequest {
  platform: NotificationPlatform;
  webhookUrl: string;
  severityThreshold: SeverityThreshold;
  weeklyReportEnabled: boolean;
}

/**
 * 알림 설정 수정 요청 바디
 * PATCH /api/v1/notifications/{id}
 */
export interface UpdateNotificationRequest {
  isActive?: boolean;
  severityThreshold?: SeverityThreshold;
  weeklyReportEnabled?: boolean;
}

// ─── 백엔드 Raw 타입 ────────────────────────────────────────────────────────────

interface RawNotificationConfig {
  id: string;
  platform: NotificationPlatform;
  webhook_url: string;
  severity_threshold: SeverityThreshold;
  weekly_report_enabled: boolean;
  is_active: boolean;
  created_at: string;
}

// ─── 변환 헬퍼 ─────────────────────────────────────────────────────────────────

function toNotificationConfig(raw: RawNotificationConfig): NotificationConfig {
  return {
    id: raw.id,
    platform: raw.platform,
    webhookUrl: raw.webhook_url,
    severityThreshold: raw.severity_threshold,
    weeklyReportEnabled: raw.weekly_report_enabled,
    isActive: raw.is_active,
    createdAt: raw.created_at,
  };
}

// ─── API 함수 ──────────────────────────────────────────────────────────────────

/**
 * 알림 설정 목록 조회
 * GET /api/v1/notifications
 */
export async function getNotifications(): Promise<NotificationConfig[]> {
  const response = await apiClient.get<ApiResponse<RawNotificationConfig[]>>(
    '/api/v1/notifications',
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '알림 설정 목록을 가져오지 못했습니다.');
  }
  return response.data.data.map(toNotificationConfig);
}

/**
 * 알림 설정 등록
 * POST /api/v1/notifications
 */
export async function createNotification(
  data: CreateNotificationRequest,
): Promise<NotificationConfig> {
  const response = await apiClient.post<ApiResponse<RawNotificationConfig>>(
    '/api/v1/notifications',
    {
      platform: data.platform,
      webhook_url: data.webhookUrl,
      severity_threshold: data.severityThreshold,
      weekly_report_enabled: data.weeklyReportEnabled,
    },
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '알림 설정 등록에 실패했습니다.');
  }
  return toNotificationConfig(response.data.data);
}

/**
 * 알림 설정 수정 (활성화/비활성화 등)
 * PATCH /api/v1/notifications/{id}
 */
export async function updateNotification(
  id: string,
  data: UpdateNotificationRequest,
): Promise<NotificationConfig> {
  const body: Record<string, unknown> = {};
  if (data.isActive !== undefined) body['is_active'] = data.isActive;
  if (data.severityThreshold !== undefined) body['severity_threshold'] = data.severityThreshold;
  if (data.weeklyReportEnabled !== undefined) body['weekly_report_enabled'] = data.weeklyReportEnabled;

  const response = await apiClient.patch<ApiResponse<RawNotificationConfig>>(
    `/api/v1/notifications/${id}`,
    body,
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '알림 설정 수정에 실패했습니다.');
  }
  return toNotificationConfig(response.data.data);
}

/**
 * 알림 설정 삭제
 * DELETE /api/v1/notifications/{id}
 */
export async function deleteNotification(id: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<unknown>>(
    `/api/v1/notifications/${id}`,
  );
  if (!response.data.success) {
    throw new Error(response.data.error ?? '알림 설정 삭제에 실패했습니다.');
  }
}

/**
 * 알림 테스트 발송
 * POST /api/v1/notifications/{id}/test
 */
export async function testNotification(id: string): Promise<void> {
  const response = await apiClient.post<ApiResponse<unknown>>(
    `/api/v1/notifications/${id}/test`,
  );
  if (!response.data.success) {
    throw new Error(response.data.error ?? '테스트 발송에 실패했습니다.');
  }
}
