import type { Page } from '@playwright/test';

// ─── 공통 mock 데이터 (snake_case — API Raw 포맷) ──────────────────────────────

export const mockUser = {
  github_login: 'testuser',
  avatar_url: null,
  email: 'test@example.com',
};

// 스캔 목록 (RawScanSummary 포맷)
export const rawMockScans = [
  {
    id: 'scan-uuid-0001',
    repo_id: 'repo-uuid-0001',
    repo_full_name: 'testuser/my-app',
    status: 'completed',
    trigger_type: 'manual',
    findings_count: 3,
    true_positives_count: 3,
    started_at: '2026-03-01T10:00:00Z',
    completed_at: '2026-03-01T10:00:42Z',
    created_at: '2026-03-01T10:00:00Z',
  },
  {
    id: 'scan-uuid-0002',
    repo_id: 'repo-uuid-0002',
    repo_full_name: 'testuser/api-server',
    status: 'running',
    trigger_type: 'webhook',
    findings_count: 0,
    true_positives_count: 0,
    started_at: '2026-03-06T09:00:00Z',
    completed_at: null,
    created_at: '2026-03-06T09:00:00Z',
  },
];

// 스캔 상세 (RawScanDetail 포맷)
export const rawMockScanDetail = {
  id: 'scan-uuid-0001',
  repo_id: 'repo-uuid-0001',
  status: 'completed',
  trigger_type: 'manual',
  commit_sha: 'abc1234',
  branch: 'main',
  pr_number: null,
  findings_count: 3,
  true_positives_count: 3,
  false_positives_count: 0,
  duration_seconds: 42,
  error_message: null,
  started_at: '2026-03-01T10:00:00Z',
  completed_at: '2026-03-01T10:00:42Z',
  created_at: '2026-03-01T10:00:00Z',
};

// 취약점 목록 (RawVulnerabilitySummary 포맷)
export const rawMockVulnerabilities = [
  {
    id: 'vuln-uuid-0001',
    status: 'open',
    severity: 'critical',
    vulnerability_type: 'sql_injection',
    file_path: 'src/db/queries.py',
    start_line: 42,
    detected_at: '2026-03-01T10:00:30Z',
    created_at: '2026-03-01T10:00:30Z',
  },
  {
    id: 'vuln-uuid-0002',
    status: 'patched',
    severity: 'high',
    vulnerability_type: 'xss',
    file_path: 'src/templates/index.html',
    start_line: 15,
    detected_at: '2026-03-01T10:00:31Z',
    created_at: '2026-03-01T10:00:31Z',
  },
  {
    id: 'vuln-uuid-0003',
    status: 'open',
    severity: 'medium',
    vulnerability_type: 'hardcoded_credentials',
    file_path: 'config/settings.py',
    start_line: 8,
    detected_at: '2026-03-01T10:00:32Z',
    created_at: '2026-03-01T10:00:32Z',
  },
];

// 취약점 상세 (RawVulnerabilityDetail 포맷 — 전체 필드)
export const rawMockVulnDetail = {
  id: 'vuln-uuid-0001',
  scan_job_id: 'scan-uuid-0001',
  repo_id: 'repo-uuid-0001',
  repo_full_name: 'testuser/my-app',
  status: 'open',
  severity: 'critical',
  vulnerability_type: 'sql_injection',
  cwe_id: 'CWE-89',
  owasp_category: 'A03:2021',
  file_path: 'src/db/queries.py',
  start_line: 42,
  end_line: 44,
  code_snippet: "query = 'SELECT * FROM users WHERE id=' + user_id",
  description: 'SQL Injection 취약점이 발견되었습니다.',
  llm_reasoning: '사용자 입력이 쿼리에 직접 삽입됩니다.',
  llm_confidence: 0.95,
  semgrep_rule_id: 'python.lang.security.audit.sqli',
  references: ['https://owasp.org/A03_2021-Injection'],
  detected_at: '2026-03-01T10:00:30Z',
  resolved_at: null,
  created_at: '2026-03-01T10:00:30Z',
  patch_pr: null,
};

// 저장소 목록 (snake_case)
export const rawMockRepos = [
  {
    id: 'repo-uuid-0001',
    team_id: 'team-uuid-0001',
    github_repo_id: 100001,
    full_name: 'testuser/my-app',
    default_branch: 'main',
    is_active: true,
    last_scan_at: '2026-03-01T10:00:42Z',
    created_at: '2026-02-01T00:00:00Z',
  },
  {
    id: 'repo-uuid-0002',
    team_id: 'team-uuid-0001',
    github_repo_id: 100002,
    full_name: 'testuser/api-server',
    default_branch: 'main',
    is_active: true,
    last_scan_at: '2026-03-06T09:00:00Z',
    created_at: '2026-02-15T00:00:00Z',
  },
];

// 하위 호환용 camelCase alias
export const mockScans = rawMockScans;
export const mockVulnerabilities = rawMockVulnerabilities;
export const mockRepos = rawMockRepos;

// ─── 공통 meta ─────────────────────────────────────────────────────────────────

function pageMeta(total: number) {
  return { page: 1, per_page: 20, total, total_pages: 1 };
}

// ─── API 모킹 헬퍼 ─────────────────────────────────────────────────────────────

/**
 * 인증된 사용자로 모든 공통 API를 모킹합니다.
 * Next.js rewrite: /api/v1/* → localhost:3000/api/v1/*
 * page.route()는 브라우저 레벨에서 인터셉트 (rewrite 전)
 */
export async function mockAuthenticatedApis(page: Page) {
  // 인증 상태
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockUser }),
    }),
  );

  // 스캔 상세 (목록보다 먼저 등록 — 더 구체적인 패턴 우선)
  await page.route(/\/api\/v1\/scans\/[^/?]+/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: rawMockScanDetail }),
    }),
  );

  // 스캔 목록
  await page.route(/\/api\/v1\/scans(\?.*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: rawMockScans,
        meta: pageMeta(2),
      }),
    }),
  );

  // 취약점 상세
  await page.route(/\/api\/v1\/vulnerabilities\/[^/?]+/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: rawMockVulnDetail }),
    }),
  );

  // 취약점 목록
  await page.route(/\/api\/v1\/vulnerabilities(\?.*)?$/, (route) => {
    const url = route.request().url();
    // 필터 파라미터 파싱 (severity=critical 등)
    const filtered = rawMockVulnerabilities.filter((v) => {
      if (url.includes('severity=critical') && v.severity !== 'critical') return false;
      if (url.includes('severity=high') && v.severity !== 'high') return false;
      if (url.includes('severity=medium') && v.severity !== 'medium') return false;
      if (url.includes('severity=low') && v.severity !== 'low') return false;
      if (url.includes('status=open') && v.status !== 'open') return false;
      if (url.includes('status=patched') && v.status !== 'patched') return false;
      return true;
    });
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: filtered,
        meta: pageMeta(filtered.length),
      }),
    });
  });

  // 저장소 목록
  await page.route(/\/api\/v1\/repos(\?.*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: rawMockRepos,
        meta: pageMeta(2),
      }),
    }),
  );

  // 저장소 상세
  await page.route(/\/api\/v1\/repos\/[^/?]+/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: rawMockRepos[0] }),
    }),
  );

  // 대시보드
  await page.route(/\/api\/v1\/dashboard/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          total_vulnerabilities: 15,
          open_vulnerabilities: 10,
          patched_vulnerabilities: 4,
          false_positives: 1,
          security_score: 72,
          critical_count: 2,
          high_count: 5,
          medium_count: 6,
          low_count: 2,
        },
      }),
    }),
  );

  // 알림
  await page.route(/\/api\/v1\/notifications/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: [], meta: pageMeta(0) }),
    }),
  );

  // 오탐
  await page.route(/\/api\/v1\/false-positives/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: [], meta: pageMeta(0) }),
    }),
  );

  // 리포트
  await page.route(/\/api\/v1\/reports/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: [], meta: pageMeta(0) }),
    }),
  );

  // 설정 / API 키
  await page.route(/\/api\/v1\/(settings|api-keys)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: {} }),
    }),
  );
}
