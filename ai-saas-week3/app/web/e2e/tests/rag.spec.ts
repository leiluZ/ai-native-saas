import { test, expect } from "@playwright/test";
import path from "path";

test.describe("RAG Pipeline - Week3", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const ragButton = page.locator('button:has-text("RAG Pipeline")');
    if (await ragButton.isVisible()) {
      await ragButton.click();
    }
  });

  test("should display RAG panel with upload functionality", async ({
    page,
  }) => {
    const uploadArea = page.locator("text=Upload Documents");
    await expect(uploadArea).toBeVisible({ timeout: 5000 });
  });

  test("should show chunk settings", async ({ page }) => {
    const chunkSizeLabel = page.locator("text=Chunk Size");
    await expect(chunkSizeLabel).toBeVisible({ timeout: 5000 });

    const strategyLabel = page.locator("text=Chunk Strategy");
    await expect(strategyLabel).toBeVisible();
  });

  test("should allow text input for RAG", async ({ page }) => {
    const textTab = page.locator('button:has-text("Text Input")');
    if (await textTab.isVisible()) {
      await textTab.click();
    }
    const textArea = page.locator("textarea").first();
    await expect(textArea).toBeVisible();
  });

  test("should upload file via file input", async ({ page }) => {
    const fileInput = page.locator("#file-upload");
    await expect(fileInput).toBeAttached();

    const testFilePath = path.join(__dirname, "../fixtures/test-document.txt");
    await fileInput.setInputFiles(testFilePath);

    const fileName = page.locator("text=test-document.txt");
    await expect(fileName).toBeVisible({ timeout: 5000 });
  });
});
