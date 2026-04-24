# Day 1 Practices (AI-Native 启动日)

目标：在 `ai-saas-week1` 项目里完成可用的 AI 开发基线，包括规则文件、可运行的 `pre-commit`、以及可验证的本地提交流程。

## 0. 前置信息确认

- 仓库根目录：`/Users/leilu/Documents/cursor_projects/ai-native-saas`
- 业务项目目录：`/Users/leilu/Documents/cursor_projects/ai-native-saas/ai-saas-week1`
- 当前 Python 来自 Homebrew（PEP 668），不建议用 `pip install --user pre-commit`
- 推荐安装方式：`pipx`

---

## 1. 安装 pre-commit（通过 pipx）

在终端执行：

```bash
brew install pipx
pipx ensurepath
```

然后重开终端（或执行 `source ~/.zshrc`），继续：

```bash
pipx install pre-commit
pre-commit --version
which pre-commit
```

验收标准：

- `pre-commit --version` 输出版本号
- `which pre-commit` 输出实际路径（不是 `not found`）

---

## 2. 确认规则文件位置

这两个文件必须在仓库根目录：

- `.editorconfig`
- `.pre-commit-config.yaml`

正确路径示例：

- `/Users/leilu/Documents/cursor_projects/ai-native-saas/.editorconfig`
- `/Users/leilu/Documents/cursor_projects/ai-native-saas/.pre-commit-config.yaml`

---

## 3. 安装 Git hooks

```bash
cd /Users/leilu/Documents/cursor_projects/ai-native-saas
pre-commit install
pre-commit install --hook-type pre-push
```

说明：

- `pre-commit install`：在 `git commit` 前执行检查
- `--hook-type pre-push`：在 `git push` 前执行更重检查（如 build）

验收标准：

- 命令输出包含 `installed`，且无报错

---

## 4. 首次全量检查

```bash
cd /Users/leilu/Documents/cursor_projects/ai-native-saas
pre-commit run --all-files
```

如果失败：

1. 根据输出修复问题（格式问题通常会自动修）
2. 再次运行 `pre-commit run --all-files`
3. 直到全部通过

---

## 5. 理解当前项目触发逻辑（按目录）

当前项目是 TS monorepo 风格：

- `ai-saas-week1/app/api`
- `ai-saas-week1/app/web`
- `ai-saas-week1/packages/shared`

当前策略：

- `commit` 阶段：基础格式与文件安全检查 + prettier
- `pre-push` 阶段：
  - 改到 `app/api` 或 `packages/shared` -> 执行 API build
  - 改到 `app/web` 或 `packages/shared` -> 执行 Web build
  - 改到 `packages/shared` -> 执行 shared build

---

## 6. 做一次生效验证（建议必做）

步骤：

1. 随便改一个 `.ts` 文件，故意制造格式问题（如尾随空格）
2. 运行：

```bash
git add .
git commit -m "test pre-commit hooks"
```

3. 确认 commit 时 hook 自动触发并修复/阻断

再验证 pre-push：

```bash
pre-commit run --hook-stage pre-push --all-files
```

---

## 7. Day 1 交付物清单

- [ ] `pre-commit` 可执行（`pre-commit --version` 正常）
- [ ] 根目录规则文件就位（`.editorconfig`、`.pre-commit-config.yaml`）
- [ ] `pre-commit install` 和 `pre-commit install --hook-type pre-push` 已执行
- [ ] `pre-commit run --all-files` 通过
- [ ] 至少一次真实 commit 触发 hook 并验证有效

---

## 8. 常见问题与处理

- `command not found: pre-commit`
  - 执行 `pipx ensurepath`，然后重开终端
- `externally-managed-environment`
  - 这是 Homebrew Python 的正常保护，使用 `pipx`，不要强行 `--break-system-packages`
- pre-push 太慢
  - 属于正常现象（会跑 build），建议保留以避免坏代码进入远端

---

## 9. Day 1 完成判定

满足以下全部条件即可判定 Day 1 完成：

1. 代码风格和提交质量检查自动化可用
2. 本地提交前可自动拦截明显问题
3. push 前可自动做关键构建验证
4. 团队/未来自己拉代码后可一键复现同样规则
