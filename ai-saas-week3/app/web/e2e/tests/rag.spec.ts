import { test, expect } from "@playwright/test";

test.describe("RAG Pipeline - Week3", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const week3Button = page.locator('button:has-text("Week3 RAG Pipeline")');
    if (await week3Button.isVisible()) {
      await week3Button.click();
    }
  });

  test("should display RAG panel with upload functionality", async ({
    page,
  }) => {
    const uploadArea = page.locator("text=上传文档");
    await expect(uploadArea).toBeVisible({ timeout: 5000 });
  });

  test("should show chunk settings", async ({ page }) => {
    const chunkSizeLabel = page.locator("text=分块大小");
    await expect(chunkSizeLabel).toBeVisible({ timeout: 5000 });

    const strategyLabel = page.locator("text=分块策略");
    await expect(strategyLabel).toBeVisible();
  });

  test("should allow text input for RAG", async ({ page }) => {
    const textArea = page.locator("textarea").first();
    await expect(textArea).toBeVisible();
  });
});
