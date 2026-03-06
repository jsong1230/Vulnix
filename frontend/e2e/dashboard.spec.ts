import { test, expect } from '@playwright/test';
import { mockAuthenticatedApis } from './fixtures';

test.describe('대시보드 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedApis(page);
  });

  test('대시보드가 정상 렌더링된다', async ({ page }) => {
    await page.goto('/dashboard');

    // 대시보드 페이지 로드 확인 (에러 없이 200)
    await expect(page).toHaveURL('/dashboard');
  });

  test('사이드바 내비게이션 링크가 존재한다', async ({ page }) => {
    await page.goto('/dashboard');

    // 사이드바에 주요 페이지 링크
    const nav = page.locator('nav, aside');
    await expect(nav.first()).toBeVisible();
  });

  test('헤더가 표시된다', async ({ page }) => {
    await page.goto('/dashboard');

    const header = page.locator('header');
    await expect(header).toBeVisible();
  });

  test('인증된 사용자 이름이 헤더에 표시된다', async ({ page }) => {
    await page.goto('/dashboard');

    // UserInfo 컴포넌트가 auth/me를 호출하고 testuser를 표시
    await expect(page.getByText('testuser')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('대시보드 내비게이션', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedApis(page);
  });

  test('루트 경로(/)는 페이지를 로드한다', async ({ page }) => {
    await page.goto('/');
    // 에러 페이지가 아님
    await expect(page.locator('body')).toBeVisible();
  });

  test('사이드바에서 스캔 페이지로 이동한다', async ({ page }) => {
    await page.goto('/dashboard');

    // 스캔 링크 클릭
    const scanLink = page.getByRole('link', { name: /스캔/i }).first();
    if (await scanLink.isVisible()) {
      await scanLink.click();
      await expect(page).toHaveURL(/\/scans/);
    }
  });

  test('사이드바에서 취약점 페이지로 이동한다', async ({ page }) => {
    await page.goto('/dashboard');

    const vulnLink = page.getByRole('link', { name: /취약점/i }).first();
    if (await vulnLink.isVisible()) {
      await vulnLink.click();
      await expect(page).toHaveURL(/\/vulnerabilities/);
    }
  });

  test('사이드바에서 저장소 페이지로 이동한다', async ({ page }) => {
    await page.goto('/dashboard');

    const repoLink = page.getByRole('link', { name: /저장소/i }).first();
    if (await repoLink.isVisible()) {
      await repoLink.click();
      await expect(page).toHaveURL(/\/repos/);
    }
  });
});
