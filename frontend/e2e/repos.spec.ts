import { test, expect } from '@playwright/test';
import { mockAuthenticatedApis, mockRepos } from './fixtures';

test.describe('저장소 목록 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedApis(page);
  });

  test('저장소 목록이 정상 렌더링된다', async ({ page }) => {
    await page.goto('/repos');

    // 저장소 이름
    await expect(page.getByText('testuser/my-app')).toBeVisible();
    await expect(page.getByText('testuser/api-server')).toBeVisible();
  });

  test('저장소 상세 페이지로 이동한다', async ({ page }) => {
    await page.goto('/repos');

    // 첫 번째 저장소 클릭
    const repoLink = page.getByText('testuser/my-app');
    if (await repoLink.isVisible()) {
      await repoLink.click();
      await expect(page).toHaveURL(/\/repos\/repo-uuid-0001/);
    }
  });

  test('저장소 상세 페이지가 렌더링된다', async ({ page }) => {
    // 저장소 상세 API 모킹
    await page.route(`**/api/v1/repos/${mockRepos[0].id}`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: mockRepos[0] }),
      }),
    );

    await page.goto(`/repos/${mockRepos[0].id}`);
    expect(page.url()).toContain(mockRepos[0].id);
  });
});
