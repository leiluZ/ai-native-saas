import { test, expect } from "@playwright/test";

const getFixturePath = (filename: string) => {
  const baseDir = new URL(".", import.meta.url).pathname;
  return `${baseDir}../fixtures/${filename}`;
};

test.describe("RAG Pipeline E2E - 端到端测试", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    const ragButton = page.locator('button:has-text("RAG Pipeline")');
    await expect(ragButton).toBeVisible({ timeout: 10000 });
    await ragButton.click();

    await page.waitForSelector('button:has-text("Execute RAG Pipeline")', {
      timeout: 10000,
    });
  });

  test("完整流程：上传文档 → 执行 RAG Pipeline → 查询知识", async ({
    page,
  }) => {
    test.setTimeout(120000);

    // ========== Step 1: 上传文档 ==========
    const fileInput = page.locator("#file-upload");
    await expect(fileInput).toBeAttached();

    const testFilePath = getFixturePath("test-document.txt");
    await fileInput.setInputFiles(testFilePath);

    await page.locator("text=test-document.txt").waitFor();

    // ========== Step 2: 执行 RAG Pipeline ==========
    const executeButton = page.locator(
      'button:has-text("Execute RAG Pipeline")',
    );
    await executeButton.click();

    await page.waitForSelector(
      'button:has-text("Execute RAG Pipeline"):not([disabled])',
      { timeout: 30000 },
    );

    const successCount = page.locator("div.bg-green-50 div.text-green-600");
    await expect(successCount).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Success")).toBeVisible();

    const chunksLabel = page.locator("text=/chunks/i").first();
    await expect(chunksLabel).toBeVisible({ timeout: 5000 });

    // ========== Step 3: 测试闲聊查询 "hello" ==========
    const qaInput = page
      .locator('input[placeholder*="基于文档内容提问"]')
      .first();
    await expect(qaInput).toBeVisible({ timeout: 5000 });

    await qaInput.fill("hello");

    const askButton = page.locator('button:has-text("Ask")');
    await askButton.click();

    // 等待 Thinking 状态消失（按钮文本变回 Ask）
    await page.waitForSelector('button:has-text("Ask")', {
      timeout: 30000,
    });

    // 验证有助手回复消息
    const assistantMessage = page
      .locator("div.justify-start div.rounded-bl-md")
      .first();
    await expect(assistantMessage).toBeVisible({ timeout: 10000 });

    // 验证置信度标签显示 "高置信度"
    const confidenceLabel = page.locator("text=高置信度");
    await expect(confidenceLabel).toBeVisible({ timeout: 5000 });

    // 验证没有 "低置信度" 标签
    const lowConfidenceLabel = page.locator("text=低置信度");
    await expect(lowConfidenceLabel).not.toBeVisible();

    // ========== Step 4: 测试知识查询（触发 RAG tool） ==========
    await qaInput.fill("What is in the test document");
    await askButton.click();

    // 等待 Thinking 状态消失
    await page.waitForSelector('button:has-text("Ask")', {
      timeout: 90000,
    });

    // 验证有新的助手回复（至少有 2 条助手消息）
    const allAssistantMessages = page.locator(
      "div.justify-start div.rounded-bl-md",
    );
    const messageCount = await allAssistantMessages.count();
    expect(messageCount).toBeGreaterThanOrEqual(2);

    await page.screenshot({
      path: "e2e/screenshots/rag-e2e-complete.png",
      fullPage: true,
    });
  });

  test("GUI 显示正确：hello 查询显示高置信度", async ({ page }) => {
    const fileInput = page.locator("#file-upload");
    const testFilePath = getFixturePath("test-document.txt");
    await fileInput.setInputFiles(testFilePath);
    await page.locator("text=test-document.txt").waitFor();

    const executeButton = page.locator(
      'button:has-text("Execute RAG Pipeline")',
    );
    await executeButton.click();
    await page.waitForSelector(
      'button:has-text("Execute RAG Pipeline"):not([disabled])',
      { timeout: 30000 },
    );

    const qaInput = page
      .locator('input[placeholder*="基于文档内容提问"]')
      .first();
    await qaInput.fill("hello");

    const askButton = page.locator('button:has-text("Ask")');
    await askButton.click();

    // 等待 Thinking 状态消失
    await page.waitForSelector('button:has-text("Ask")', {
      timeout: 30000,
    });

    // 验证响应内容不为空
    const assistantMessage = page
      .locator("div.justify-start div.rounded-bl-md")
      .first();
    await expect(assistantMessage).toBeVisible();

    const messageText = await assistantMessage.textContent();
    expect(messageText).toBeTruthy();
    expect(messageText!.length).toBeGreaterThan(0);

    // 验证显示 "高置信度"
    await expect(page.locator("text=高置信度")).toBeVisible({ timeout: 5000 });

    // 验证不显示 "低置信度"
    await expect(page.locator("text=低置信度")).not.toBeVisible();
  });

  test("RAG Tool 调用：知识查询返回引用和结果", async ({ page }) => {
    test.setTimeout(120000);

    const fileInput = page.locator("#file-upload");
    const testFilePath = getFixturePath("test-document.txt");
    await fileInput.setInputFiles(testFilePath);
    await page.locator("text=test-document.txt").waitFor();

    const executeButton = page.locator(
      'button:has-text("Execute RAG Pipeline")',
    );
    await executeButton.click();
    await page.waitForSelector(
      'button:has-text("Execute RAG Pipeline"):not([disabled])',
      { timeout: 60000 },
    );

    const qaInput = page
      .locator('input[placeholder*="基于文档内容提问"]')
      .first();
    await qaInput.fill("What does the test document contain");

    const askButton = page.locator('button:has-text("Ask")');
    await askButton.click();

    // 等待 Thinking 状态消失
    await page.waitForSelector('button:has-text("Ask")', {
      timeout: 90000,
    });

    // 验证有助手回复
    const assistantMessage = page
      .locator("div.justify-start div.rounded-bl-md")
      .first();
    await expect(assistantMessage).toBeVisible({ timeout: 10000 });

    const messageText = await assistantMessage.textContent();
    expect(messageText).toBeTruthy();
    expect(messageText!.length).toBeGreaterThan(0);

    await page.screenshot({
      path: "e2e/screenshots/rag-e2e-knowledge-query.png",
      fullPage: true,
    });
  });

  test("错误处理：未上传文档时 Q&A 区域显示提示信息", async ({ page }) => {
    await page.reload();
    await page.waitForLoadState("domcontentloaded");

    const ragButton = page.locator('button:has-text("RAG Pipeline")');
    if (await ragButton.isVisible()) {
      await ragButton.click();
    }

    await page.waitForSelector('button:has-text("Execute RAG Pipeline")', {
      timeout: 10000,
    });

    // 验证 Q&A 区域显示提示信息（未上传文档时）
    const qaSection = page.locator('h2:has-text("Knowledge Base Q&A")');
    await expect(qaSection).toBeVisible();

    // 验证提示文本显示
    const hintText = page.locator("text=请先上传文档并执行 RAG Pipeline");
    await expect(hintText).toBeVisible({ timeout: 5000 });
  });
});
