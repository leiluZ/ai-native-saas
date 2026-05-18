# Week 11: 作品集打磨与开源贡献

## 🎯 目标
提升 GitHub 活跃度与技术影响力。完成仓库合规化审计、高转化率 README 重构、2 篇深度技术博客、1 个开源 PR 提交、3 分钟 Demo 视频录制与个人 Portfolio 站点搭建，形成可传播、可验证的技术品牌资产。

---

## Day 1：仓库审计（结构/License/敏感信息清理）

- **目标**：建立符合开源标准的仓库基线，消除安全与合规风险，规范目录结构。
- **实操**：
  1. 使用 `gitleaks` / `trufflehog` / `git-secrets` 全量扫描 Commit 历史，清理硬编码的 API Key、密码、私有 IP。
  2. 配置 `.gitignore` 与 `.gitattributes`，清理 `__pycache__`、`.env`、大文件（大文件启用 Git LFS）。
  3. 规范化目录结构：`src/`、`scripts/`、`configs/`、`docs/`、`tests/`，补充 `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`。
  4. 选择并注入开源协议（推荐 MIT 或 Apache-2.0），在 `package.json`/`pyproject.toml` 中声明。
  5. 添加 Issue/PR 模板：`ISSUE_TEMPLATE.md` 和 `PULL_REQUEST_TEMPLATE.md`。
  6. 清理 commit 历史中的大文件（BFG Repo-Cleaner 或 git filter-branch）。
- **Prompt 模板**：

```md
编写开源仓库合规化审计与重构脚本，要求：

1. 自动化扫描：gitleaks/trufflehog 全量检测 Commit 历史，输出泄漏清单与修复命令
2. 目录重构：按 src/scripts/configs/tests/docs 标准化拆分
3. 忽略策略：.gitignore 覆盖 20+ 常见冗余文件，.gitattributes 配置文本/二进制/LFS 规则
4. 协议注入：生成 LICENSE/CONTRIBUTING/CODE_OF_CONDUCT，支持 MIT/Apache2.0 一键切换
5. 安全基线：校验仓库权限、Webhook 配置、依赖锁文件完整性，输出合规检查报告
6. 保留完整 Git 历史，清理仅作用于敏感文件，不重写公共 Commit
```

- **验收**：
  - ✅ 零敏感信息残留，Git LFS 接管 > 100MB 文件
  - ✅ 目录结构符合社区规范，`.gitignore` 覆盖完整
  - ✅ License/CONTRIBUTING/Issue/PR 模板齐备，合规报告 100% 通过

## Day 2：README 重构（Mermaid 架构/快速启动/AI 声明）

- **目标**：打造高转化率 README，降低 Fork/Star 门槛，明确 AI 辅助边界。
- **实操**：
  1. 编写项目简介：一句话描述 + 核心亮点（3-5 个 Bullet）+ Shields.io 徽章（CI/Coverage/License/Python）。
  2. 设计 Mermaid 架构图：展示数据流、模块交互、外部依赖（vLLM/Redis/DB）。
  3. 编写 Quick Start：环境要求 → 安装依赖 → 配置环境变量 → 一键启动（`docker-compose up` 或 `make dev`）。
  4. 编写 API 文档概览：核心端点 + 请求/响应示例 + Swagger 链接。
  5. 添加 AI 辅助声明：说明项目 AI 辅助比例（约 60%）、使用工具、人工审核流程。
  6. 补充 `Features`、`Performance`（压测数据）、`Roadmap`、`FAQ`。
- **Prompt 模板**：

```md
生成高转化率开源 README 模板，要求：

1. 标准 Markdown 结构：Title/Badges/架构图/简介/快速开始/核心特性/压测数据/Roadmap/许可协议
2. Mermaid 架构图：清晰展示数据流、服务依赖、异步链路，支持 GitHub 原生渲染
3. Quick Start：3 步内跑通（安装 → 配置 → 启动），附 Docker/源码双模式命令与预期输出
4. AI 声明模块：明确工具使用范围、人工 Review 比例、结果可复现性说明
5. SEO 优化：关键词布局、内部链接锚点、多语言目录预留（/docs/zh-CN）
6. 输出可直接替换的 README.md，附 Shields 徽章生成链接
```

- **验收**：
  - ✅ 架构图清晰可交互，Mermaid 渲染正常
  - ✅ Quick Start 3 步内跑通，无环境依赖阻塞
  - ✅ AI 声明透明合规，徽章/目录/FAQ 完善
  - ✅ 新用户 5 分钟内理解项目并能跑起来

## Day 3：技术博客 #1（Agent 多智能体协作落地）

- **目标**：沉淀复杂 AI 工作流实战经验，建立技术影响力。
- **实操**：
  1. 选题：基于 Week 4-5 实战，聚焦 LangGraph 多 Agent 协作。
  2. 结构设计：业务痛点 → LangGraph 状态机设计 → 多 Agent 路由策略 → 工具调用与回退 → 生产调优。
  3. 嵌入核心代码片段（带行号高亮），绘制 Agent 交互时序图与状态流转图（Mermaid）。
  4. 提供完整可运行 Notebook/脚本，附依赖安装与运行命令。
  5. 适配多平台发布（掘金/知乎/Medium/个人博客），配置 SEO Meta 标签与封面图。
- **Prompt 模板**：

```md
撰写 LangGraph 多 Agent 实战技术博客，要求：

1. 结构：痛点引入 → 架构设计 → 核心代码 → 踩坑与调优 → 生产建议 → 完整 Demo 仓库链接
2. 图表：Mermaid 状态机流转图、Agent 协作时序图、性能对比柱状图（延迟/成本/成功率）
3. 代码规范：关键片段带行号注释，提供完整可运行的 Jupyter/Python 脚本
4. 平台适配：Markdown 原始文件 + 平台排版指南（代码块/封面/标签/SEO 关键词）
5. 价值主张：突出"可落地、可复现、可扩展"，避免纯理论堆砌
```

- **验收**：
  - ✅ 逻辑严密，含可独立运行的代码与数据集
  - ✅ 架构图/时序图专业，压测数据真实可复现
  - ✅ 平台排版优化完成，SEO 标签完整
  - ✅ 阅读量 ≥ 500（首周）或收到 ≥ 3 条评论

## Day 4：技术博客 #2（vLLM 部署与推理加速）

- **目标**：分享底层推理优化经验，吸引后端/Infra 开发者关注。
- **实操**：
  1. 聚焦 PagedAttention 原理、KV Cache 调优、AWQ/GPTQ 量化对比、高并发压测。
  2. 提供 `docker-compose.yml`、Nginx 反向代理配置、Prometheus 抓取模板。
  3. 对比优化前后指标：P99 延迟、吞吐（QPS）、显存利用率、GPU 计算饱和度。
  4. 编写 FAQ：常见 OOM、代理断流、并发排队、版本兼容性解决方案。
  5. 适配多平台发布，配置 SEO Meta 标签与封面图。
- **Prompt 模板**：

```md
撰写 vLLM 生产部署与推理加速技术博客，要求：

1. 结构：引擎原理简述 → 部署架构 → KV Cache 调优 → 量化策略 → 压测对比 → 避坑指南
2. 数据驱动：提供真实 Benchmark 脚本与结果（CSV/图表），对比 Ollama/vLLM/原生推理
3. 配置模板：完整 docker-compose、Nginx 代理、Prometheus scrape_config，开箱即用
4. FAQ 模块：覆盖 OOM、SSE 断流、并发排队、CUDA 版本冲突、模型兼容性
5. 生产建议：监控指标阈值、扩缩容策略、降级路由、成本控制
```

- **验收**：
  - ✅ 数据真实可复现，配置模板一键拉起
  - ✅ 覆盖 vLLM 核心调优点，FAQ 解决 80% 常见报错
  - ✅ 图表专业，压测数据可追溯

## Day 5：开源 PR 提交（LangChain/vLLM 文档或 Bug 修复）

- **目标**：融入头部开源生态，积累贡献者信誉与社区背书。
- **实操**：
  1. 在目标仓库筛选 `good first issue` 或文档缺失/过时 Issue（推荐 LangChain/vLLM/llama.cpp/Taro）。
  2. Fork → 创建分支 `fix/docs-xxx` → 编写修复代码/文档 → 本地运行测试与 Lint。
  3. 遵循社区规范：Conventional Commits、PR 模板、测试覆盖、变更日志。
  4. 撰写清晰 PR 描述：背景、复现步骤、修改点、测试截图、关联 Issue。
  5. 跟进 Review 反馈，及时修改。
- **Prompt 模板**：

```md
生成开源 PR 提交全流程指南与模板，要求：

1. Issue 分析：复现环境搭建、日志收集、根因定位路径、修复边界确认
2. PR 规范：Conventional Commits 格式，PR 描述模板（Background/Fix/Test/Screenshot）
3. 本地验证：单元测试执行、Lint/Type-Check 通过、构建无警告
4. 维护者沟通：专业术语对齐、响应超时处理、代码 Review 反馈跟进话术
5. CI 预检：模拟 GitHub Actions 运行环境，提前拦截格式/依赖/兼容性问题
```

- **验收**：
  - ✅ PR 符合社区规范，CI 全绿
  - ✅ 描述清晰，复现与修复步骤完整可验证
  - ✅ ≥ 1 个 PR 提交，进入 Review 或已 Merge

## Day 6：3 分钟 Demo 视频录制

- **目标**：直观展示项目价值，提升传播转化率与 GitHub 曝光。
- **实操**：
  1. 编写分镜脚本：痛点引入（15s）→ 核心功能演示（60s）→ 架构/性能亮点（60s）→ 一键部署（30s）→ 结尾引导（15s）。
  2. 使用 OBS 录制 1080p/60fps，开启鼠标高亮、键盘按键显示、系统音频隔离。
  3. 剪映/iMovie/Davinci Resolve 剪辑：加速冗余操作、添加中英文字幕、关键帧高亮标注、BGM 降噪。
  4. 设计封面图（Canva 快速生成），上传 YouTube/Bilibili/GitHub Releases，嵌入 README。
  5. 优化视频 SEO：标题、描述、标签、置顶评论引导 Star/Fork。
- **Prompt 模板**：

```md
规划并生成 3 分钟技术 Demo 视频分镜与剪辑脚本，要求：

1. 节奏控制：痛点 15s → 演示 60s → 架构 60s → 部署 30s → 引导 15s，总时长 180s
2. 录制参数：1080p/60fps，开启鼠标轨迹/按键显示，禁用无关通知与系统音
3. 剪辑要求：去除等待/报错片段，关键操作 1.5x 倍速，添加中英文字幕与高亮框
4. 封面设计：项目 Logo + 核心标语 + 架构图局部，对比度 > 4.5:1，16:9
5. 发布清单：B站/YouTube/GitHub 标签优化、简介 SEO、置顶评论引导 Star/Fork
```

- **验收**：
  - ✅ 时长 2.5~3min，节奏紧凑无废话
  - ✅ 核心功能 100% 展示，音画同步无卡顿
  - ✅ 字幕/高亮/封面专业，全平台上传成功

## Day 7：个人 Portfolio 页面搭建

- **目标**：集中展示技术成果，打造个人品牌流量入口与求职/合作名片。
- **实操**：
  1. 选择静态站点生成器（Astro/Next.js/Hugo），部署至 Vercel/Netlify/GitHub Pages。
  2. 集成 GitHub API：自动拉取 Star/PR/贡献数据，生成项目卡片与活跃度曲线。
  3. 页面板块：Hero（头像 + 姓名 + 定位）→ Projects（项目卡片含截图/Demo 链接）→ Blog → GitHub Stats → Contact。
  4. GitHub Profile README 增强：添加个人简介、技能标签、GitHub Stats、本周动态。
  5. 配置 SEO、Sitemap、暗色模式、响应式布局，Lighthouse 性能优化（> 90 分）。
- **Prompt 模板**：

```md
构建高性能个人 Portfolio 站点，要求：

1. 技术栈：Astro/Next.js + Tailwind，部署 Vercel/GitHub Pages，零后端依赖
2. GitHub 集成：自动拉取 Star/PR/贡献数据，动态生成项目卡片与活跃度图表
3. 模块设计：Hero/精选项目/技术博客/技术栈/联系方式/Resume，暗色模式切换
4. 性能优化：SSG/ISR 缓存、图片懒加载、字体子集化，Lighthouse 评分 > 90
5. SEO 配置：Sitemap/Robots/OpenGraph/JSON-LD，支持自定义域名与 HTTPS
6. 输出完整项目模板、部署脚本、数据同步 GitHub Action、SEO 校验报告
```

- **验收**：
  - ✅ 页面加载 < 2s，Lighthouse > 90 分
  - ✅ 数据自动同步，移动端/桌面端完美适配
  - ✅ SEO 评分达标，自定义域名解析生效
  - ✅ 模块完整，Resume/联系方式一键可达

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 零敏感信息泄露；目录结构规范；License/CONTRIBUTING 齐备；合规报告 100% |
| D2 | 架构图清晰可交互；Quick Start 3 步内跑通；AI 声明透明；徽章/FAQ 完善 |
| D3 | 博客逻辑严密含可运行代码；架构图/数据真实；平台排版优化完成；获基础互动 |
| D4 | vLLM 配置一键拉起；压测数据可复现；FAQ 覆盖 80% 常见报错；社区转发 |
| D5 | PR 符合规范 CI 全绿；描述清晰可验证；Maintainer Review 中；测盖 > 85% |
| D6 | 时长 2.5~3min；核心功能完整展示；音画/字幕专业；多平台上传成功 |
| D7 | Lighthouse > 90；数据自动同步；暗色/响应式完美；自定义域名与 SEO 生效 |

## 最终验收标准

- ✅ README 专业完整，Star/Fork 友好，3 步内可本地跑通，AI 声明透明合规
- ✅ 2 篇深度技术博客发布，数据真实可复现，获技术社区互动/转发
- ✅ 1 个开源 PR 进入 Review，CI 全绿，符合社区规范
- ✅ 3 分钟 Demo 视频节奏紧凑、音画达标，全平台上传成功
- ✅ 个人 Portfolio 站点加载 < 2s，GitHub 数据自动同步，Lighthouse > 90
- ✅ 完整技术资产包归档：合规仓库、博客源文件、PR 链接、视频工程、Portfolio 源码

## 高频 Prompt 模板

1. **开源仓库合规审计 Prompt**
   - gitleaks 扫描与敏感信息清理
   - 目录标准化与 .gitignore/.gitattributes 配置
   - License/CONTRIBUTING 注入与 Git 历史保留

2. **高转化率 README 重构 Prompt**
   - Mermaid 架构图与 Quick Start 3 步指南
   - 压测数据展示与 Roadmap 规划
   - AI 辅助声明与 Shields 徽章生成

3. **LangGraph 多 Agent 实战博客 Prompt**
   - 状态机设计与时序图嵌入规范
   - 核心代码片段与完整可运行脚本
   - 多平台排版适配与 SEO 关键词优化

4. **vLLM 部署与推理加速博客 Prompt**
   - PagedAttention/KV Cache/量化策略详解
   - 真实 Benchmark 数据与配置模板
   - 生产避坑 FAQ 与监控扩缩容建议

5. **开源 PR 提交流程 Prompt**
   - Issue 复现与根因定位路径
   - Conventional Commits 与 PR 描述模板
   - CI 预检与维护者沟通跟进话术

6. **3 分钟 Demo 视频分镜 Prompt**
   - 节奏控制与 OBS 录制参数配置
   - 剪辑加速/字幕/高亮规范
   - 封面设计与多平台发布 Checklist

7. **个人 Portfolio 站点搭建 Prompt**
   - Astro/Next.js + Tailwind 静态生成
   - GitHub API 数据自动同步
   - Lighthouse > 90 优化与 SEO 完整配置

## 动态调整建议

- **无视频剪辑经验**：
  - D6 使用 CapCut/剪映模板一键生成字幕/高亮，优先保证内容完整。
- **PR 被拒或长期无响应**：
  - D5 转向文档类 PR（错别字/示例更新/配置说明），通过率更高。
- **博客流量低/无互动**：
  - D3/D4 结尾添加"可运行 Repo + 一键部署"降低读者尝试门槛，主动投稿至技术社区。
- **时间紧张/并行任务多**：
  - D1/D2 优先使用 GitHub Community Health Files 快速生成基线；D7 采用 Hugo/Carrd 等低代码模板。
- **非英语技术背景**：
  - 博客/Demo/README 优先中文发布，同步生成英文摘要（AI 辅助翻译 + 人工校对）。

## 第 7 天自测清单

- [ ] 仓库零敏感信息，目录结构规范，License/CONTRIBUTING 完备，gitleaks 扫描通过
- [ ] README 含 Mermaid 架构图、3 步 Quick Start、AI 声明、Shields 徽章、移动端适配良好
- [ ] LangGraph 博客发布，含状态机图/可运行代码/压测数据，多平台排版完成
- [ ] vLLM 博客发布，配置模板一键拉起，FAQ 覆盖常见报错，数据真实可复现
- [ ] 开源 PR 已提交，CI 全绿，PR 描述规范，Maintainer 进入 Review 或已合并
- [ ] 3min Demo 视频剪辑完成，音画同步/字幕专业，B站/YouTube/GitHub 上传成功
- [ ] Portfolio 站点上线，GitHub 数据自动同步，Lighthouse > 90，自定义域名解析生效
- [ ] 仓库包含：合规审计报告、README.md、博客源文件、PR 链接、视频工程、Portfolio 源码
- [ ] 能清晰口述：开源合规基线、高转化 README 设计逻辑、AI 工作流实战经验、推理加速核心指标、PR 贡献流程与个人品牌运营策略
