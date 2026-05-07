import { test, expect } from "@playwright/test";

test.describe("Tools Functionality - Week1", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("should send message and receive response", async ({ page }) => {
    const inputLocator = page.locator("textarea");
    const sendButton = page
      .locator("button")
      .filter({ has: page.locator("svg") })
      .last();

    await inputLocator.fill("Hello, how are you?");
    await sendButton.click();

    await page.waitForTimeout(5000);

    const messages = page.locator('[class*="rounded-2xl"]');
    await expect(messages.last()).toBeVisible({ timeout: 10000 });
  });

  test("should display loading state while waiting for response", async ({
    page,
  }) => {
    const inputLocator = page.locator("textarea");
    const sendButton = page
      .locator("button")
      .filter({ has: page.locator("svg") })
      .last();

    await inputLocator.fill("Hello");
    await sendButton.click();

    const loadingIndicator = page.locator(
      ".animate-bounce, [class*='animate-spin']",
    );
    await expect(loadingIndicator.first()).toBeVisible({ timeout: 5000 });
  });

  test("should clear messages when clicking clear button", async ({ page }) => {
    const inputLocator = page.locator("textarea");
    const sendButton = page
      .locator("button")
      .filter({ has: page.locator("svg") })
      .last();
    const clearButton = page.locator(
      'button[title*="清空"], button:has([class*="lucide-trash"])',
    );

    await inputLocator.fill("Test message");
    await sendButton.click();
    await page.waitForTimeout(3000);

    await clearButton.click();

    const messages = page.locator('[class*="rounded-2xl"]');
    const count = await messages.count();
    expect(count).toBeLessThanOrEqual(1);
  });

  test("should toggle theme when clicking theme button", async ({ page }) => {
    const themeButton = page.locator(
      'button[title*="模式"], button:has([class*="lucide-moon"]), button:has([class*="lucide-sun"])',
    );
    await expect(themeButton).toBeVisible();

    await themeButton.click();
    await page.waitForTimeout(500);

    await themeButton.click();
  });
});
