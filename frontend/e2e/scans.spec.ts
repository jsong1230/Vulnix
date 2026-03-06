import { test, expect } from '@playwright/test';
import { mockAuthenticatedApis, rawMockScans } from './fixtures';

test.describe('스캔 목록 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedApis(page);
  });

  test('스캔 목록이 정상 렌더링된다', async ({ page }) => {
    await page.goto('/scans');

    // 페이지 제목
    await expect(page.getByRole('heading', { name: '스캔 이력' })).toBeVisible();

    // 스캔 항목이 표시됨
    await expect(page.getByText('testuser/my-app')).toBeVisible();
    await expect(page.getByText('testuser/api-server')).toBeVisible();
  });

  test('완료된 스캔에 찾은 건수가 표시된다', async ({ page }) => {
    await page.goto('/scans');

    // completed 스캔: findings_count=3 (tabular-nums span)
    await expect(page.locator('.tabular-nums').filter({ hasText: '3' })).toBeVisible();
  });

  test('실행 중인 스캔에 "스캔 중" 상태 배지가 표시된다', async ({ page }) => {
    await page.goto('/scans');
    await expect(page.getByText('스캔 중')).toBeVisible();
  });

  test('완료된 스캔에 "완료" 상태 배지가 표시된다', async ({ page }) => {
    await page.goto('/scans');
    await expect(page.getByText('완료')).toBeVisible();
  });

  test('스캔 행 클릭 시 상세 페이지로 이동한다', async ({ page }) => {
    await page.goto('/scans');

    // 첫 번째 스캔 클릭
    await page.getByText('testuser/my-app').click();

    await expect(page).toHaveURL(/\/scans\/scan-uuid-0001/);
  });
});

test.describe('스캔 상세 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedApis(page);
  });

  test('스캔 상세 정보가 렌더링된다', async ({ page }) => {
    await page.goto(`/scans/${rawMockScans[0].id}`);

    // 완료 상태 배지
    await expect(page.getByText('완료')).toBeVisible();
  });

  test('스캔 ID가 URL에 포함되어 있다', async ({ page }) => {
    await page.goto(`/scans/${rawMockScans[0].id}`);
    expect(page.url()).toContain(rawMockScans[0].id);
  });

  test('스캔 목록 페이지로 돌아가는 링크가 있다', async ({ page }) => {
    await page.goto(`/scans/${rawMockScans[0].id}`);

    const backLink = page.getByRole('link', { name: /스캔/i }).first();
    await expect(backLink).toBeVisible();
  });
});
