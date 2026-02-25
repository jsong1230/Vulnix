/**
 * 스캔 & 취약점 관련 API 클라이언트
 * F-04 설계서 4절 API 설계 기준
 */
import { apiClient, type ApiResponse } from './api-client';

// ─── 타입 정의 ─────────────────────────────────────────────────────────────────

/** 스캔 작업 상태 */
export type ScanStatus = 'queued' | 'running' | 'completed' | 'failed';

/** 취약점 심각도 */
export type Severity = 'critical' | 'high' | 'medium' | 'low';

/** 취약점 처리 상태 */
export type VulnerabilityStatus = 'open' | 'patched' | 'ignored' | 'false_positive';

/**
 * 스캔 작업 상세 정보
 * GET /api/v1/scans/{scan_id} 응답 data
 */
export interface ScanDetail {
  id: string;
  repoId: string;
  status: ScanStatus;
  triggerType: 'manual' | 'webhook' | 'schedule';
  commitSha: string | null;
  branch: string | null;
  prNumber: number | null;
  findingsCount: number;
  truePositivesCount: number;
  falsePositivesCount: number;
  durationSeconds: number | null;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

/**
 * 취약점 목록 항목 (요약)
 * GET /api/v1/vulnerabilities 응답 data[] 항목
 */
export interface VulnerabilitySummary {
  id: string;
  status: VulnerabilityStatus;
  severity: Severity;
  vulnerabilityType: string;
  filePath: string;
  startLine: number;
  detectedAt: string;
  createdAt: string;
}

/**
 * 패치 PR 요약 정보
 * 취약점 상세 응답에 포함
 */
export interface PatchPRSummary {
  id: string;
  githubPrNumber: number | null;
  githubPrUrl: string | null;
  status: string;
  patchDiff: string | null;
  patchDescription: string | null;
}

/**
 * 취약점 상세 정보
 * GET /api/v1/vulnerabilities/{vuln_id} 응답 data
 */
export interface VulnerabilityDetail {
  id: string;
  scanJobId: string;
  repoId: string;
  status: VulnerabilityStatus;
  severity: Severity;
  vulnerabilityType: string;
  cweId: string | null;
  owaspCategory: string | null;
  filePath: string;
  startLine: number;
  endLine: number;
  codeSnippet: string | null;
  description: string | null;
  llmReasoning: string | null;
  llmConfidence: number | null;
  semgrepRuleId: string | null;
  references: string[];
  detectedAt: string;
  resolvedAt: string | null;
  createdAt: string;
  patchPr: PatchPRSummary | null;
  repoFullName: string | null;
}

/**
 * 페이지네이션 메타 정보
 */
export interface PaginationMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

/**
 * 페이지네이션 응답 래퍼
 */
export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginationMeta;
}

/**
 * 최근 스캔 항목
 * 대시보드 요약 응답에 포함
 */
export interface RecentScanItem {
  id: string;
  repoFullName: string;
  status: ScanStatus;
  findingsCount: number;
  truePositivesCount: number;
  createdAt: string;
}

/**
 * 대시보드 요약 통계
 * GET /api/v1/dashboard/summary 응답 data
 */
export interface DashboardSummary {
  totalVulnerabilities: number;
  severityDistribution: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  statusDistribution: {
    open: number;
    patched: number;
    ignored: number;
    false_positive: number;
  };
  resolutionRate: number;
  recentScans: RecentScanItem[];
  repoCount: number;
  lastScanAt: string | null;
}

/**
 * 취약점 목록 조회 필터 파라미터
 */
export interface VulnerabilityListParams {
  repoId?: string;
  severity?: Severity;
  status?: VulnerabilityStatus;
  page?: number;
  perPage?: number;
}

// ─── 백엔드 Raw 타입 (스네이크케이스) ────────────────────────────────────────────

interface RawScanDetail {
  id: string;
  repo_id: string;
  status: ScanStatus;
  trigger_type: 'manual' | 'webhook' | 'schedule';
  commit_sha: string | null;
  branch: string | null;
  pr_number: number | null;
  findings_count: number;
  true_positives_count: number;
  false_positives_count: number;
  duration_seconds: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface RawVulnerabilitySummary {
  id: string;
  status: VulnerabilityStatus;
  severity: Severity;
  vulnerability_type: string;
  file_path: string;
  start_line: number;
  detected_at: string;
  created_at: string;
}

interface RawPatchPRSummary {
  id: string;
  github_pr_number: number | null;
  github_pr_url: string | null;
  status: string;
  patch_diff: string | null;
  patch_description: string | null;
}

interface RawVulnerabilityDetail {
  id: string;
  scan_job_id: string;
  repo_id: string;
  status: VulnerabilityStatus;
  severity: Severity;
  vulnerability_type: string;
  cwe_id: string | null;
  owasp_category: string | null;
  file_path: string;
  start_line: number;
  end_line: number;
  code_snippet: string | null;
  description: string | null;
  llm_reasoning: string | null;
  llm_confidence: number | null;
  semgrep_rule_id: string | null;
  references: string[];
  detected_at: string;
  resolved_at: string | null;
  created_at: string;
  patch_pr: RawPatchPRSummary | null;
  repo_full_name: string | null;
}

interface RawRecentScanItem {
  id: string;
  repo_full_name: string;
  status: ScanStatus;
  findings_count: number;
  true_positives_count: number;
  created_at: string;
}

interface RawDashboardSummary {
  total_vulnerabilities: number;
  severity_distribution: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  status_distribution: {
    open: number;
    patched: number;
    ignored: number;
    false_positive: number;
  };
  resolution_rate: number;
  recent_scans: RawRecentScanItem[];
  repo_count: number;
  last_scan_at: string | null;
}

// ─── 변환 헬퍼 ─────────────────────────────────────────────────────────────────

function toScanDetail(raw: RawScanDetail): ScanDetail {
  return {
    id: raw.id,
    repoId: raw.repo_id,
    status: raw.status,
    triggerType: raw.trigger_type,
    commitSha: raw.commit_sha,
    branch: raw.branch,
    prNumber: raw.pr_number,
    findingsCount: raw.findings_count,
    truePositivesCount: raw.true_positives_count,
    falsePositivesCount: raw.false_positives_count,
    durationSeconds: raw.duration_seconds,
    errorMessage: raw.error_message,
    startedAt: raw.started_at,
    completedAt: raw.completed_at,
    createdAt: raw.created_at,
  };
}

function toVulnerabilitySummary(raw: RawVulnerabilitySummary): VulnerabilitySummary {
  return {
    id: raw.id,
    status: raw.status,
    severity: raw.severity,
    vulnerabilityType: raw.vulnerability_type,
    filePath: raw.file_path,
    startLine: raw.start_line,
    detectedAt: raw.detected_at,
    createdAt: raw.created_at,
  };
}

function toPatchPRSummary(raw: RawPatchPRSummary): PatchPRSummary {
  return {
    id: raw.id,
    githubPrNumber: raw.github_pr_number,
    githubPrUrl: raw.github_pr_url,
    status: raw.status,
    patchDiff: raw.patch_diff,
    patchDescription: raw.patch_description,
  };
}

function toVulnerabilityDetail(raw: RawVulnerabilityDetail): VulnerabilityDetail {
  return {
    id: raw.id,
    scanJobId: raw.scan_job_id,
    repoId: raw.repo_id,
    status: raw.status,
    severity: raw.severity,
    vulnerabilityType: raw.vulnerability_type,
    cweId: raw.cwe_id,
    owaspCategory: raw.owasp_category,
    filePath: raw.file_path,
    startLine: raw.start_line,
    endLine: raw.end_line,
    codeSnippet: raw.code_snippet,
    description: raw.description,
    llmReasoning: raw.llm_reasoning,
    llmConfidence: raw.llm_confidence,
    semgrepRuleId: raw.semgrep_rule_id,
    references: raw.references,
    detectedAt: raw.detected_at,
    resolvedAt: raw.resolved_at,
    createdAt: raw.created_at,
    patchPr: raw.patch_pr ? toPatchPRSummary(raw.patch_pr) : null,
    repoFullName: raw.repo_full_name,
  };
}

function toRecentScanItem(raw: RawRecentScanItem): RecentScanItem {
  return {
    id: raw.id,
    repoFullName: raw.repo_full_name,
    status: raw.status,
    findingsCount: raw.findings_count,
    truePositivesCount: raw.true_positives_count,
    createdAt: raw.created_at,
  };
}

function toDashboardSummary(raw: RawDashboardSummary): DashboardSummary {
  return {
    totalVulnerabilities: raw.total_vulnerabilities,
    severityDistribution: raw.severity_distribution,
    statusDistribution: raw.status_distribution,
    resolutionRate: raw.resolution_rate,
    recentScans: raw.recent_scans.map(toRecentScanItem),
    repoCount: raw.repo_count,
    lastScanAt: raw.last_scan_at,
  };
}

// ─── API 함수 ──────────────────────────────────────────────────────────────────

/**
 * 스캔 상세 조회
 * GET /api/v1/scans/{scanId}
 */
export async function getScan(scanId: string): Promise<ScanDetail> {
  const response = await apiClient.get<ApiResponse<RawScanDetail>>(
    `/api/v1/scans/${scanId}`,
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '스캔 정보를 가져오지 못했습니다.');
  }
  return toScanDetail(response.data.data);
}

/**
 * 취약점 목록 조회 (필터 지원)
 * GET /api/v1/vulnerabilities
 */
export async function getVulnerabilities(
  params: VulnerabilityListParams,
): Promise<PaginatedResponse<VulnerabilitySummary>> {
  const queryParams: Record<string, string | number> = {};
  if (params.repoId) queryParams.repo_id = params.repoId;
  if (params.severity) queryParams.severity = params.severity;
  if (params.status) queryParams.status = params.status;
  if (params.page) queryParams.page = params.page;
  if (params.perPage) queryParams.per_page = params.perPage;

  const response = await apiClient.get<ApiResponse<RawVulnerabilitySummary[]>>(
    '/api/v1/vulnerabilities',
    { params: queryParams },
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '취약점 목록을 가져오지 못했습니다.');
  }

  // 백엔드 응답의 meta 필드에는 total_pages가 추가로 포함됨 (설계서 4-2절)
  // ApiResponse.meta 기본 타입에 없으므로 unknown 경유로 안전하게 접근
  const rawMeta = response.data.meta as (typeof response.data.meta & { total_pages?: number }) | undefined;
  return {
    items: response.data.data.map(toVulnerabilitySummary),
    meta: {
      page: rawMeta?.page ?? 1,
      per_page: rawMeta?.per_page ?? 20,
      total: rawMeta?.total ?? 0,
      total_pages: rawMeta?.total_pages ?? 1,
    },
  };
}

/**
 * 취약점 상세 조회
 * GET /api/v1/vulnerabilities/{vulnId}
 */
export async function getVulnerability(vulnId: string): Promise<VulnerabilityDetail> {
  const response = await apiClient.get<ApiResponse<RawVulnerabilityDetail>>(
    `/api/v1/vulnerabilities/${vulnId}`,
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '취약점 정보를 가져오지 못했습니다.');
  }
  return toVulnerabilityDetail(response.data.data);
}

/**
 * 취약점 상태 변경
 * PATCH /api/v1/vulnerabilities/{vulnId}
 */
export async function patchVulnerabilityStatus(
  vulnId: string,
  status: VulnerabilityStatus,
  reason?: string,
): Promise<VulnerabilityDetail> {
  const response = await apiClient.patch<ApiResponse<RawVulnerabilityDetail>>(
    `/api/v1/vulnerabilities/${vulnId}`,
    { status, reason },
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '취약점 상태 변경에 실패했습니다.');
  }
  return toVulnerabilityDetail(response.data.data);
}

/**
 * 대시보드 요약 통계 조회
 * GET /api/v1/dashboard/summary
 */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  const response = await apiClient.get<ApiResponse<RawDashboardSummary>>(
    '/api/v1/dashboard/summary',
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '대시보드 요약을 가져오지 못했습니다.');
  }
  return toDashboardSummary(response.data.data);
}
