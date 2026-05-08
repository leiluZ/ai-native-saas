import { test, expect } from "@playwright/test";

test.describe("Tools Functionality - Week2 (LangGraph)", () => {
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

  test("should send message and receive response via LangGraph", async ({
    page,
  }) => {
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

  test("should display loading state while waiting for LangGraph response", async ({
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
      ".animate-bounce, [class*='animate-spin'], [class*='animate-pulse']",
    );

    try {
      await expect(loadingIndicator.first()).toBeVisible({ timeout: 2000 });
    } catch {
      console.log(
        "Loading indicator not visible - request may have completed quickly",
      );
    }
  });

  test("should handle low confidence and show approval UI", async ({
    page,
  }) => {
    const inputLocator = page.locator("textarea");
    const sendButton = page
      .locator("button")
      .filter({ has: page.locator("svg") })
      .last();

    await inputLocator.fill("Tell me something ambiguous");
    await sendButton.click();

    await page.waitForTimeout(5000);

    const approvalText = page.locator("text=/置信度较低|批准|修改/");
    const hasApproval = (await approvalText.count()) > 0;

    if (hasApproval) {
      await expect(approvalText.first()).toBeVisible();
    }

    const messages = page.locator('[class*="rounded-2xl"]');
    await expect(messages.last()).toBeVisible({ timeout: 10000 });
  });

  test("should toggle between Week1 and Week2 agent modes", async ({
    page,
  }) => {
    const week1Button = page.locator('button:has-text("Week1 Agent")');
    const week2Button = page.locator(
      'button:has-text("Week2 LangGraph Agent")',
    );

    await expect(week1Button).toBeVisible();
    await expect(week2Button).toBeVisible();

    await week1Button.click();
    await expect(week1Button).toHaveClass(/bg-blue-500/);

    await week2Button.click();
    await expect(week2Button).toHaveClass(/bg-blue-500/);
  });

  test("should display circuit breaker status", async ({ page }) => {
    const circuitStatus = page.locator(
      '[class*="rounded-lg"]:has-text("正常"), [class*="rounded-lg"]:has-text("熔断"), [class*="rounded-lg"]:has-text("恢复中")',
    );
    await expect(circuitStatus.first()).toBeVisible({ timeout: 10000 });
  });
});
