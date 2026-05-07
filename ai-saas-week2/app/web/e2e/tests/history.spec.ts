import { test, expect } from "@playwright/test";

test.describe("History Display - Week2 (LangGraph)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const week2Button = page.locator(
      'button:has-text("Week2 LangGraph Agent")',
    );
    if (await week2Button.isVisible()) {
      await week2Button.click();
    }
  });

  test("should open history modal when clicking history button", async ({
    page,
  }) => {
    const historyButton = page.locator(
      'button[title*="历史"], button:has([class*="lucide-history"])',
    );
    await expect(historyButton).toBeVisible();

    await historyButton.click();

    const historyModal = page.locator('[class*="fixed"][class*="inset-0"]');
    await expect(historyModal.first()).toBeVisible({ timeout: 5000 });
  });

  test("should close history modal when clicking X button", async ({
    page,
  }) => {
    const historyButton = page.locator(
      'button[title*="历史"], button:has([class*="lucide-history"])',
    );
    await historyButton.click();

    await page.waitForTimeout(1000);

    const closeButton = page.locator('button:has([class*="lucide-x"])');
    await expect(closeButton.first()).toBeVisible();
    await closeButton.first().click();

    await page.waitForTimeout(500);

    const historyModal = page.locator('[class*="fixed"][class*="inset-0"]');
    await expect(historyModal.first()).not.toBeVisible({ timeout: 3000 });
  });

  test("should send messages and then view history", async ({ page }) => {
    const inputLocator = page.locator("textarea");
    const sendButton = page
      .locator("button")
      .filter({ has: page.locator("svg") })
      .last();

    await inputLocator.fill("First test message");
    await sendButton.click();
    await page.waitForTimeout(2000);

    await inputLocator.fill("Second test message");
    await sendButton.click();
    await page.waitForTimeout(2000);

    const messages = page.locator('[class*="rounded-2xl"]');
    const count = await messages.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const historyButton = page.locator(
      'button[title*="历史"], button:has([class*="lucide-history"])',
    );
    await historyButton.click();

    await page.waitForTimeout(2000);

    const historyModal = page.locator('[class*="fixed"][class*="inset-0"]');
    await expect(historyModal.first()).toBeVisible({ timeout: 5000 });
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

    await inputLocator.fill("Test message for clearing");
    await sendButton.click();
    await page.waitForTimeout(3000);

    await clearButton.click();

    const messages = page.locator('[class*="rounded-2xl"]');
    const count = await messages.count();
    expect(count).toBeLessThanOrEqual(1);
  });
});
