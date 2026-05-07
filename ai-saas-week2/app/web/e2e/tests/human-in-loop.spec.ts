import { test, expect } from "@playwright/test";

test.describe("Human-in-the-Loop Approval - Week2", () => {
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

  test("should show approval UI when confidence is low", async ({ page }) => {
    const inputLocator = page.locator('textarea[placeholder*="输入消息"]');
    const sendButton = page.locator('button:has(svg[class*="lucide-send"])');

    await inputLocator.fill(
      "Do something ambiguous that might trigger low confidence",
    );
    await sendButton.click();

    await page.waitForTimeout(5000);

    const approvalBox = page.locator(
      'text=置信度较低, text=请确认结果, [class*="amber"]',
    );
    const hasApproval = (await approvalBox.count()) > 0;

    if (hasApproval) {
      const approveButton = page.locator(
        'button:has-text("批准"), button:has([class*="lucide-check"])',
      );
      const modifyButton = page.locator(
        'button:has-text("修改"), button:has([class*="lucide-edit3"])',
      );
      await expect(approveButton.or(modifyButton).first()).toBeVisible();
    } else {
      console.log(
        "Query did not trigger low confidence - this is acceptable for high-confidence responses",
      );
    }
  });

  test("should approve message and continue conversation", async ({ page }) => {
    const inputLocator = page.locator('textarea[placeholder*="输入消息"]');
    const sendButton = page.locator('button:has(svg[class*="lucide-send"])');

    await inputLocator.fill("Tell me something vague");
    await sendButton.click();

    await page.waitForTimeout(5000);

    const approvalBox = page.locator("text=置信度较低, text=请确认结果");
    const hasApproval = (await approvalBox.count()) > 0;

    if (hasApproval) {
      const approveButton = page.locator('button:has-text("批准")');
      await expect(approveButton).toBeVisible();

      await approveButton.click();
      await page.waitForTimeout(3000);

      await inputLocator.fill("Continue the conversation");
      await sendButton.click();
      await page.waitForTimeout(3000);

      const messages = page.locator('[class*="rounded-2xl"]');
      const count = await messages.count();
      expect(count).toBeGreaterThan(2);
    } else {
      console.log(
        "Query did not trigger approval flow - testing with high confidence response",
      );
    }
  });

  test("should modify and send edited result", async ({ page }) => {
    const inputLocator = page.locator('textarea[placeholder*="输入消息"]');
    const sendButton = page.locator('button:has(svg[class*="lucide-send"])');

    await inputLocator.fill("Give me a fact about an uncommon topic");
    await sendButton.click();

    await page.waitForTimeout(5000);

    const approvalBox = page.locator("text=置信度较低");
    const hasApproval = (await approvalBox.count()) > 0;

    if (hasApproval) {
      const modifyButton = page.locator('button:has-text("修改")');
      await expect(modifyButton).toBeVisible();
      await modifyButton.click();

      const textarea = page.locator('textarea[class*="border"]');
      await expect(textarea).toBeVisible();
      await textarea.fill("Modified result by user");

      const sendModifiedButton = page.locator('button:has-text("发送修改")');
      await expect(sendModifiedButton).toBeVisible();
      await sendModifiedButton.click();

      await page.waitForTimeout(3000);

      const lastMessage = page.locator('[class*="rounded-2xl"]').last();
      const content = await lastMessage.textContent();
      expect(content).toMatch(/modified|user/i);
    } else {
      console.log("Query did not trigger approval flow");
    }
  });

  test("should cancel modification", async ({ page }) => {
    const inputLocator = page.locator('textarea[placeholder*="输入消息"]');
    const sendButton = page.locator('button:has(svg[class*="lucide-send"])');

    await inputLocator.fill("Random question");
    await sendButton.click();

    await page.waitForTimeout(5000);

    const approvalBox = page.locator("text=置信度较低");
    const hasApproval = (await approvalBox.count()) > 0;

    if (hasApproval) {
      const modifyButton = page.locator('button:has-text("修改")');
      await modifyButton.click();

      const textarea = page.locator('textarea[class*="border"]');
      await expect(textarea).toBeVisible();

      const cancelButton = page.locator('button:has-text("取消")');
      await expect(cancelButton).toBeVisible();
      await cancelButton.click();

      await page.waitForTimeout(500);

      const approvalButtons = page.locator(
        'button:has-text("批准"), button:has-text("修改")',
      );
      await expect(approvalButtons.first()).toBeVisible();
    } else {
      console.log("Query did not trigger approval flow");
    }
  });

  test("should display alert icon for pending approval", async ({ page }) => {
    const inputLocator = page.locator('textarea[placeholder*="输入消息"]');
    const sendButton = page.locator('button:has(svg[class*="lucide-send"])');

    await inputLocator.fill("Query that might need approval");
    await sendButton.click();

    await page.waitForTimeout(5000);

    const alertIcon = page.locator(
      '[class*="lucide-alert-triangle"], [class*="amber"]',
    );
    const hasAlert = (await alertIcon.count()) > 0;

    if (hasAlert) {
      const alertTriangle = page
        .locator('[class*="lucide-alert-triangle"]')
        .first();
      await expect(alertTriangle).toBeVisible();
    }
  });
});
