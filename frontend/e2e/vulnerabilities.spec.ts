import { test, expect } from '@playwright/test';
import { mockAuthenticatedApis, rawMockVulnerabilities } from './fixtures';

test.describe('취약점 목록 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedApis(page);
  });

  test('취약점 목록이 정상 렌더링된다', async ({ page }) => {
    await page.goto('/vulnerabilities');

    // 페이지 제목
    await expect(page.getByRole('heading', { name: '취약점 목록' })).toBeVisible();

    // 취약점 항목 (vulnerability_type → 프론트에서 그대로 표시)
    await expect(page.getByText('sql_injection')).toBeVisible();
    await expect(page.getByText('xss')).toBeVisible();
    await expect(page.getByText('hardcoded_credentials')).toBeVisible();
  });

  test('파일 경로가 표시된다', async ({ page }) => {
    await page.goto('/vulnerabilities');

    await expect(page.getByText('src/db/queries.py')).toBeVisible();
    await expect(page.getByText('src/templates/index.html')).toBeVisible();
  });

  test('심각도 배지가 표시된다', async ({ page }) => {
    await page.goto('/vulnerabilities');

    // 테이블 내 배지 (span.rounded.border) - 필터 버튼 제외
    const table = page.locator('.divide-y');
    await expect(table.getByText('Critical').first()).toBeVisible();
    await expect(table.getByText('High').first()).toBeVisible();
    await expect(table.getByText('Medium').first()).toBeVisible();
  });

  test('처리 상태 배지가 표시된다', async ({ page }) => {
    await page.goto('/vulnerabilities');

    const table = page.locator('.divide-y');
    await expect(table.getByText('Open').first()).toBeVisible();
    await expect(table.getByText('Patched').first()).toBeVisible();
  });

  test('총 건수가 표시된다', async ({ page }) => {
    await page.goto('/vulnerabilities');
    await expect(page.getByText('총 3건')).toBeVisible();
  });

  test('심각도 필터 버튼이 표시된다', async ({ page }) => {
    await page.goto('/vulnerabilities');

    await expect(page.getByRole('button', { name: '전체' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Critical' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'High' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Medium' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Low' })).toBeVisible();
  });

  test('심각도 필터 클릭 시 해당 취약점만 표시된다', async ({ page }) => {
    await page.goto('/vulnerabilities');

    // Critical 필터 클릭
    await page.getByRole('button', { name: 'Critical' }).click();

    // Critical 취약점만 표시, High는 안 보임
    await expect(page.getByText('sql_injection')).toBeVisible();
    await expect(page.getByText('xss')).not.toBeVisible();
  });

  test('상태 필터 버튼이 표시된다', async ({ page }) => {
    await page.goto('/vulnerabilities');

    await expect(page.getByRole('button', { name: 'Open' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Patched' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Ignored' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'False Positive' })).toBeVisible();
  });

  test('취약점 행 클릭 시 상세 페이지로 이동한다', async ({ page }) => {
    await page.goto('/vulnerabilities');

    await page.getByText('sql_injection').click();
    await expect(page).toHaveURL(/\/vulnerabilities\/vuln-uuid-0001/);
  });
});

test.describe('취약점 상세 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedApis(page);
  });

  test('취약점 상세가 렌더링된다', async ({ page }) => {
    await page.goto(`/vulnerabilities/${rawMockVulnerabilities[0].id}`);

    // 취약점 타입 제목이 표시됨
    await expect(page.getByRole('heading', { name: 'sql_injection' })).toBeVisible();
  });

  test('상세 페이지 URL이 올바르다', async ({ page }) => {
    await page.goto(`/vulnerabilities/${rawMockVulnerabilities[0].id}`);
    expect(page.url()).toContain(rawMockVulnerabilities[0].id);
  });
});
