/**
 * 오탐 패턴 관련 API 클라이언트
 * 오탐 패턴 CRUD
 */
import { apiClient, type ApiResponse } from './api-client';

// ─── 타입 정의 ─────────────────────────────────────────────────────────────────

/**
 * 오탐 패턴 항목
 * GET /api/v1/false-positives 응답 data[] 항목
 */
export interface FalsePositivePattern {
  id: string;
  semgrepRuleId: string;
  filePattern: string | null;
  reason: string;
  isActive: boolean;
  createdBy: string;
  createdAt: string;
}

/**
 * 오탐 패턴 등록 요청 바디
 * POST /api/v1/false-positives
 */
export interface CreateFalsePositiveRequest {
  semgrepRuleId: string;
  filePattern?: string;
  reason: string;
}

/**
 * 오탐 패턴 수정 요청 바디
 * PATCH /api/v1/false-positives/{id}
 */
export interface UpdateFalsePositiveRequest {
  isActive?: boolean;
}

// ─── 백엔드 Raw 타입 ────────────────────────────────────────────────────────────

interface RawFalsePositivePattern {
  id: string;
  semgrep_rule_id: string;
  file_pattern: string | null;
  reason: string;
  is_active: boolean;
  created_by: string;
  created_at: string;
}

// ─── 변환 헬퍼 ─────────────────────────────────────────────────────────────────

function toFalsePositivePattern(raw: RawFalsePositivePattern): FalsePositivePattern {
  return {
    id: raw.id,
    semgrepRuleId: raw.semgrep_rule_id,
    filePattern: raw.file_pattern,
    reason: raw.reason,
    isActive: raw.is_active,
    createdBy: raw.created_by,
    createdAt: raw.created_at,
  };
}

// ─── API 함수 ──────────────────────────────────────────────────────────────────

/**
 * 오탐 패턴 목록 조회
 * GET /api/v1/false-positives
 */
export async function getFalsePositives(): Promise<FalsePositivePattern[]> {
  const response = await apiClient.get<ApiResponse<RawFalsePositivePattern[]>>(
    '/api/v1/false-positives',
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '오탐 패턴 목록을 가져오지 못했습니다.');
  }
  return response.data.data.map(toFalsePositivePattern);
}

/**
 * 오탐 패턴 등록
 * POST /api/v1/false-positives
 */
export async function createFalsePositive(
  data: CreateFalsePositiveRequest,
): Promise<FalsePositivePattern> {
  const response = await apiClient.post<ApiResponse<RawFalsePositivePattern>>(
    '/api/v1/false-positives',
    {
      semgrep_rule_id: data.semgrepRuleId,
      file_pattern: data.filePattern ?? null,
      reason: data.reason,
    },
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '오탐 패턴 등록에 실패했습니다.');
  }
  return toFalsePositivePattern(response.data.data);
}

/**
 * 오탐 패턴 수정 (활성화/비활성화)
 * PATCH /api/v1/false-positives/{id}
 */
export async function updateFalsePositive(
  id: string,
  data: UpdateFalsePositiveRequest,
): Promise<FalsePositivePattern> {
  const body: Record<string, unknown> = {};
  if (data.isActive !== undefined) body['is_active'] = data.isActive;

  const response = await apiClient.patch<ApiResponse<RawFalsePositivePattern>>(
    `/api/v1/false-positives/${id}`,
    body,
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '오탐 패턴 수정에 실패했습니다.');
  }
  return toFalsePositivePattern(response.data.data);
}

/**
 * 오탐 패턴 삭제
 * DELETE /api/v1/false-positives/{id}
 */
export async function deleteFalsePositive(id: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<unknown>>(
    `/api/v1/false-positives/${id}`,
  );
  if (!response.data.success) {
    throw new Error(response.data.error ?? '오탐 패턴 삭제에 실패했습니다.');
  }
}
