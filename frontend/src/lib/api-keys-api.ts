/**
 * IDE API Key 관련 API 클라이언트
 * API Key 발급/목록 조회/비활성화
 */
import { apiClient, type ApiResponse } from './api-client';

// ─── 타입 정의 ─────────────────────────────────────────────────────────────────

/**
 * API Key 항목
 * GET /api/v1/ide/api-keys 응답 data[] 항목
 */
export interface ApiKey {
  id: string;
  name: string;
  keyPrefix: string;
  expiresAt: string | null;
  lastUsedAt: string | null;
  isActive: boolean;
  createdAt: string;
}

/**
 * API Key 발급 응답 (발급 직후 1회만 전체 키 노출)
 */
export interface ApiKeyCreated extends ApiKey {
  fullKey: string;
}

/**
 * API Key 발급 요청 바디
 * POST /api/v1/ide/api-keys
 */
export interface CreateApiKeyRequest {
  name: string;
  expiresInDays?: number;
}

// ─── 백엔드 Raw 타입 ────────────────────────────────────────────────────────────

interface RawApiKey {
  id: string;
  name: string;
  key_prefix: string;
  expires_at: string | null;
  last_used_at: string | null;
  is_active: boolean;
  created_at: string;
}

interface RawApiKeyCreated extends RawApiKey {
  full_key: string;
}

// ─── 변환 헬퍼 ─────────────────────────────────────────────────────────────────

function toApiKey(raw: RawApiKey): ApiKey {
  return {
    id: raw.id,
    name: raw.name,
    keyPrefix: raw.key_prefix,
    expiresAt: raw.expires_at,
    lastUsedAt: raw.last_used_at,
    isActive: raw.is_active,
    createdAt: raw.created_at,
  };
}

function toApiKeyCreated(raw: RawApiKeyCreated): ApiKeyCreated {
  return {
    ...toApiKey(raw),
    fullKey: raw.full_key,
  };
}

// ─── API 함수 ──────────────────────────────────────────────────────────────────

/**
 * API Key 목록 조회
 * GET /api/v1/ide/api-keys
 */
export async function getApiKeys(): Promise<ApiKey[]> {
  const response = await apiClient.get<ApiResponse<RawApiKey[]>>(
    '/api/v1/ide/api-keys',
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? 'API Key 목록을 가져오지 못했습니다.');
  }
  return response.data.data.map(toApiKey);
}

/**
 * API Key 발급
 * POST /api/v1/ide/api-keys
 * 발급된 전체 키는 응답에서 1회만 반환
 */
export async function createApiKey(
  data: CreateApiKeyRequest,
): Promise<ApiKeyCreated> {
  const response = await apiClient.post<ApiResponse<RawApiKeyCreated>>(
    '/api/v1/ide/api-keys',
    {
      name: data.name,
      expires_in_days: data.expiresInDays ?? null,
    },
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? 'API Key 발급에 실패했습니다.');
  }
  return toApiKeyCreated(response.data.data);
}

/**
 * API Key 비활성화 (삭제)
 * DELETE /api/v1/ide/api-keys/{id}
 */
export async function revokeApiKey(id: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<unknown>>(
    `/api/v1/ide/api-keys/${id}`,
  );
  if (!response.data.success) {
    throw new Error(response.data.error ?? 'API Key 비활성화에 실패했습니다.');
  }
}
