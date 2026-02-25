/**
 * 저장소 관련 API 클라이언트
 * 설계서 F-01-repo-integration.md 4절 API 설계 기준
 */
import { apiClient, type ApiResponse } from './api-client';

// ─── 타입 정의 ─────────────────────────────────────────────────────────────────

/**
 * 연동된 저장소 정보
 * GET /api/v1/repos 응답 data[] 항목
 */
export interface Repository {
  id: string;
  fullName: string;
  defaultBranch: string;
  language: string;
  isActive: boolean;
  securityScore: number | null;
  lastScannedAt: string | null;
  isInitialScanDone: boolean;
}

/**
 * GitHub App 설치 후 접근 가능한 저장소 항목
 * GET /api/v1/repos/github/installations 응답 data.repositories[] 항목
 */
export interface GitHubRepo {
  githubRepoId: number;
  fullName: string;
  isPrivate: boolean;
  defaultBranch: string;
  language: string | null;
  alreadyConnected: boolean;
}

/**
 * GitHub installations 응답 데이터
 */
export interface GitHubInstallations {
  installationId: number;
  repositories: GitHubRepo[];
}

/**
 * 저장소 연동 등록 요청 바디
 * POST /api/v1/repos
 */
export interface RegisterRepoRequest {
  githubRepoId: number;
  fullName: string;
  defaultBranch: string;
  language: string;
  installationId: number;
}

/**
 * 수동 스캔 트리거 결과
 * POST /api/v1/scans 응답 data
 */
export interface ScanJob {
  id: string;
  repoId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  triggerType: string;
  branch: string | null;
  commitSha: string | null;
  findingsCount: number;
  triggeredAt: string;
  createdAt: string;
}

/**
 * 스캔 목록 항목
 * GET /api/v1/repos/{id}/scans 응답 data[] 항목
 */
export interface ScanSummary {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  branch: string | null;
  findingsCount: number;
  durationSeconds: number | null;
  createdAt: string;
}

/**
 * 취약점 목록 항목
 * GET /api/v1/repos/{id}/vulnerabilities 응답 data[] 항목
 */
export interface VulnerabilitySummary {
  id: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  vulnerabilityType: string;
  filePath: string;
  startLine: number;
  status: 'open' | 'patched' | 'ignored' | 'false_positive';
  detectedAt: string;
}

/**
 * 백엔드 API 스네이크케이스 저장소 응답 형식
 * (API 응답 → 프론트 타입 변환 중간 타입)
 */
interface RawRepository {
  id: string;
  full_name: string;
  default_branch: string;
  language: string;
  is_active: boolean;
  security_score: number | null;
  last_scanned_at: string | null;
  is_initial_scan_done: boolean;
}

/**
 * 백엔드 API 스네이크케이스 스캔잡 응답 형식
 */
interface RawScanJob {
  id: string;
  repo_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  trigger_type: string;
  branch: string | null;
  commit_sha: string | null;
  findings_count: number;
  created_at: string;
}

/**
 * 백엔드 API 스네이크케이스 스캔 요약 응답 형식
 */
interface RawScanSummary {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  branch: string | null;
  findings_count: number;
  duration_seconds: number | null;
  created_at: string;
}

/**
 * 백엔드 API 스네이크케이스 취약점 요약 응답 형식
 */
interface RawVulnerabilitySummary {
  id: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  vulnerability_type: string;
  file_path: string;
  start_line: number;
  status: 'open' | 'patched' | 'ignored' | 'false_positive';
  detected_at: string;
}

/**
 * 백엔드 API 스네이크케이스 GitHub repo 응답 형식
 */
interface RawGitHubRepo {
  github_repo_id: number;
  full_name: string;
  private: boolean;
  default_branch: string;
  language: string | null;
  already_connected: boolean;
}

// ─── 변환 헬퍼 ─────────────────────────────────────────────────────────────────

/**
 * API 응답(스네이크케이스) → 프론트엔드 타입(카멜케이스) 변환
 */
function toRepository(raw: RawRepository): Repository {
  return {
    id: raw.id,
    fullName: raw.full_name,
    defaultBranch: raw.default_branch,
    language: raw.language,
    isActive: raw.is_active,
    securityScore: raw.security_score,
    lastScannedAt: raw.last_scanned_at,
    isInitialScanDone: raw.is_initial_scan_done,
  };
}

/**
 * API 응답(스네이크케이스) → ScanJob 타입(카멜케이스) 변환
 */
function toScanJob(raw: RawScanJob): ScanJob {
  return {
    id: raw.id,
    repoId: raw.repo_id,
    status: raw.status,
    triggerType: raw.trigger_type,
    branch: raw.branch,
    commitSha: raw.commit_sha,
    findingsCount: raw.findings_count,
    triggeredAt: raw.created_at,
    createdAt: raw.created_at,
  };
}

/**
 * API 응답(스네이크케이스) → GitHubRepo 타입(카멜케이스) 변환
 */
function toGitHubRepo(raw: RawGitHubRepo): GitHubRepo {
  return {
    githubRepoId: raw.github_repo_id,
    fullName: raw.full_name,
    isPrivate: raw.private,
    defaultBranch: raw.default_branch,
    language: raw.language,
    alreadyConnected: raw.already_connected,
  };
}

/**
 * API 응답(스네이크케이스) → ScanSummary 타입(카멜케이스) 변환
 */
function toScanSummary(raw: RawScanSummary): ScanSummary {
  return {
    id: raw.id,
    status: raw.status,
    branch: raw.branch,
    findingsCount: raw.findings_count,
    durationSeconds: raw.duration_seconds,
    createdAt: raw.created_at,
  };
}

/**
 * API 응답(스네이크케이스) → VulnerabilitySummary 타입(카멜케이스) 변환
 */
function toVulnerabilitySummary(
  raw: RawVulnerabilitySummary,
): VulnerabilitySummary {
  return {
    id: raw.id,
    severity: raw.severity,
    vulnerabilityType: raw.vulnerability_type,
    filePath: raw.file_path,
    startLine: raw.start_line,
    status: raw.status,
    detectedAt: raw.detected_at,
  };
}

// ─── API 함수 ──────────────────────────────────────────────────────────────────

/**
 * 연동된 저장소 목록 조회
 * GET /api/v1/repos
 */
export async function getRepos(): Promise<Repository[]> {
  const response = await apiClient.get<ApiResponse<RawRepository[]>>(
    '/api/v1/repos',
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '저장소 목록을 가져오지 못했습니다.');
  }
  return response.data.data.map(toRepository);
}

/**
 * GitHub App 설치된 저장소 목록 조회
 * GET /api/v1/repos/github/installations
 */
export async function getGitHubInstallations(): Promise<GitHubInstallations> {
  const response = await apiClient.get<
    ApiResponse<{ installation_id: number; repositories: RawGitHubRepo[] }>
  >('/api/v1/repos/github/installations');
  if (!response.data.success || !response.data.data) {
    throw new Error(
      response.data.error ?? 'GitHub 설치 저장소 목록을 가져오지 못했습니다.',
    );
  }
  const { installation_id, repositories } = response.data.data;
  return {
    installationId: installation_id,
    repositories: repositories.map(toGitHubRepo),
  };
}

/**
 * 저장소 연동 등록
 * POST /api/v1/repos
 */
export async function registerRepo(
  data: RegisterRepoRequest,
): Promise<Repository> {
  const response = await apiClient.post<ApiResponse<RawRepository>>(
    '/api/v1/repos',
    {
      github_repo_id: data.githubRepoId,
      full_name: data.fullName,
      default_branch: data.defaultBranch,
      language: data.language,
      installation_id: data.installationId,
    },
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '저장소 연동에 실패했습니다.');
  }
  return toRepository(response.data.data);
}

/**
 * 저장소 연동 해제
 * DELETE /api/v1/repos/{repoId}
 */
export async function deleteRepo(repoId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<unknown>>(
    `/api/v1/repos/${repoId}`,
  );
  if (!response.data.success) {
    throw new Error(response.data.error ?? '저장소 연동 해제에 실패했습니다.');
  }
}

/**
 * 저장소 단건 조회
 * GET /api/v1/repos/{repoId}
 */
export async function getRepo(repoId: string): Promise<Repository> {
  const response = await apiClient.get<ApiResponse<RawRepository>>(
    `/api/v1/repos/${repoId}`,
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '저장소 정보를 가져오지 못했습니다.');
  }
  return toRepository(response.data.data);
}

/**
 * 저장소의 최근 스캔 목록 조회
 * GET /api/v1/repos/{repoId}/scans
 */
export async function getRepoScans(repoId: string): Promise<ScanSummary[]> {
  const response = await apiClient.get<ApiResponse<RawScanSummary[]>>(
    `/api/v1/repos/${repoId}/scans`,
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '스캔 목록을 가져오지 못했습니다.');
  }
  return response.data.data.map(toScanSummary);
}

/**
 * 저장소의 취약점 목록 조회
 * GET /api/v1/repos/{repoId}/vulnerabilities
 */
export async function getRepoVulnerabilities(
  repoId: string,
): Promise<VulnerabilitySummary[]> {
  const response = await apiClient.get<ApiResponse<RawVulnerabilitySummary[]>>(
    `/api/v1/repos/${repoId}/vulnerabilities`,
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '취약점 목록을 가져오지 못했습니다.');
  }
  return response.data.data.map(toVulnerabilitySummary);
}

/**
 * 수동 스캔 트리거
 * POST /api/v1/scans
 */
export async function triggerScan(repoId: string): Promise<ScanJob> {
  const response = await apiClient.post<ApiResponse<RawScanJob>>(
    '/api/v1/scans',
    {
      repo_id: repoId,
      branch: null,
      commit_sha: null,
    },
  );
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.error ?? '스캔 트리거에 실패했습니다.');
  }
  return toScanJob(response.data.data);
}
