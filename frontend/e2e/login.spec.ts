import { test, expect } from '@playwright/test';

test.describe('로그인 페이지', () => {
  test('로그인 페이지가 정상 렌더링된다', async ({ page }) => {
    await page.goto('/login');

    // 제목 확인
    await expect(page.locator('h1')).toBeVisible();

    // Vulnix 로고 텍스트 (로그인 카드 내 large 텍스트)
    await expect(page.getByText('Vulnix').first()).toBeVisible();

    // GitHub 로그인 버튼 존재
    const loginBtn = page.getByRole('link', { name: /github/i });
    await expect(loginBtn).toBeVisible();

    // GitHub OAuth URL로 연결
    const href = await loginBtn.getAttribute('href');
    expect(href).toContain('github.com/login/oauth/authorize');
  });

  test('GitHub 로그인 버튼 클릭 시 OAuth URL로 이동한다', async ({ page }) => {
    await page.goto('/login');

    const loginBtn = page.getByRole('link', { name: /github/i });
    const href = await loginBtn.getAttribute('href');
    expect(href).toBeTruthy();
    expect(href).toContain('scope=');
  });

  test('페이지 타이틀에 Vulnix가 포함된다', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle(/Vulnix/i);
  });
});
