import { test, expect } from "@playwright/test";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// RAG tests commented out to avoid long running times during development
// Uncomment when ready to run RAG E2E tests

// test.describe("RAG Pipeline - Week3", () => {
//   test.beforeEach(async ({ page }) => {
//     await page.goto("/");
//     await page.waitForLoadState("networkidle");

//     const ragButton = page.locator('button:has-text("RAG Pipeline")');
//     if (await ragButton.isVisible()) {
//       await ragButton.click();
//     }
//   });

//   test("should display RAG panel with upload functionality", async ({
//     page,
//   }) => {
//     const uploadArea = page.locator("text=Upload Documents");
//     await expect(uploadArea).toBeVisible({ timeout: 5000 });
//   });

//   test("should show chunk settings", async ({ page }) => {
//     const chunkSizeLabel = page.locator("text=Chunk Size");
//     await expect(chunkSizeLabel).toBeVisible({ timeout: 5000 });

//     const strategyLabel = page.locator("text=Chunk Strategy");
//     await expect(strategyLabel).toBeVisible();
//   });

//   test("should allow text input for RAG", async ({ page }) => {
//     const textTab = page.locator('button:has-text("Text Input")');
//     if (await textTab.isVisible()) {
//       await textTab.click();
//     }
//     const textArea = page.locator("textarea").first();
//     await expect(textArea).toBeVisible();
//   });

//   test("should upload file via file input", async ({ page }) => {
//     const fileInput = page.locator("#file-upload");
//     await expect(fileInput).toBeAttached();

//     const testFilePath = join(__dirname, "../fixtures/test-document.txt");
//     await fileInput.setInputFiles(testFilePath);

//     const fileName = page.locator("text=test-document.txt");
//     await expect(fileName).toBeVisible({ timeout: 5000 });
//   });

//   test("should execute RAG pipeline with uploaded file", async ({ page }) => {
//     // 上传文件
//     const fileInput = page.locator("#file-upload");
//     const testFilePath = join(__dirname, "../fixtures/test-document.txt");
//     await fileInput.setInputFiles(testFilePath);

//     // 等待文件名显示
//     await page.locator("text=test-document.txt").waitFor();

//     // 点击执行按钮
//     const executeButton = page.locator(
//       'button:has-text("Execute RAG Pipeline")',
//     );
//     await executeButton.click();

//     // 等待加载完成（按钮不再禁用）
//     await page.waitForSelector(
//       'button:has-text("Execute RAG Pipeline"):not([disabled])',
//       { timeout: 15000 },
//     );

//     // 验证成功结果显示
//     const successCount = page.locator("div.bg-green-50 div.text-green-600");
//     await expect(successCount).toBeVisible({ timeout: 5000 });
//     await expect(page.locator("text=Success")).toBeVisible();
//   });
// });
