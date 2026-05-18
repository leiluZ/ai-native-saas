# Week 11: 作品集打磨与开源贡献

## 🎯 目标
提升 GitHub 活跃度与技术影响力。覆盖仓库审计与重构、README 专业化、技术博客撰写、开源 PR 提交、Demo 视频录制与个人 Portfolio 页面搭建，最终呈现专业、可展示的技术作品集。

---

## Day 1：仓库审计（结构/License/敏感信息清理）

- **目标**：审计项目仓库，优化目录结构，清理敏感信息，确保开源合规。
- **实操**：
  1. 目录结构审计：检查 `src/`、`tests/`、`docs/`、`scripts/` 目录合理性，移除冗余文件。
  2. License 文件：选择合适的开源协议（MIT/Apache 2.0/GPL），添加 `LICENSE` 文件。
  3. 敏感信息扫描：使用 `git-secrets` 或 `trufflehog` 扫描仓库历史，确保无 API Key/Token/密码泄露。
  4. `.gitignore` 审查：确保 env 文件、IDE 配置、构建产物、缓存目录已排除。
  5. Issue/PR 模板：添加 `ISSUE_TEMPLATE.md` 和 `PULL_REQUEST_TEMPLATE.md`。
  6. 清理 commit 历史中的大文件（BFG Repo-Cleaner 或 git filter-branch）。
- **Prompt 模板**：

```md
审计并优化项目仓库结构与合规性，要求：

1. 目录结构检查清单：
   - [ ] src/ 或 app/ 源码组织合理
   - [ ] tests/ 测试结构清晰，与源码对应
   - [ ] docs/ 文档目录存在
   - [ ] scripts/ 工具脚本集中管理
   - [ ] 无 .DS_Store/Thumbs.db/__pycache__ 残留
   - [ ] config/ 示例配置（.example.env）存在

2. 敏感信息扫描：
   - 使用 git-secrets --scan 或 trufflehog git file://.
   - 检查项：API_KEY, TOKEN, PASSWORD, SECRET, PRIVATE_KEY
   - 若历史提交含敏感信息：git filter-branch 或 BFG 清理
   - 旋转所有已泄露凭证

3. License 选择指南：
   - MIT：最宽松，允许商用+闭源衍生
   - Apache 2.0：含专利权保护，适合大公司
   - GPLv3：强制开源衍生作品，适合社区驱动项目

4. 社区文件：
   - CONTRIBUTING.md：贡献指南（环境搭建/代码风格/PR 流程）
   - CODE_OF_CONDUCT.md：行为准则
   - ISSUE_TEMPLATE.md：Bug Report / Feature Request 模板
   - PULL_REQUEST_TEMPLATE.md：变更说明 + Checklist
```

- **验收**：
  - 目录结构清晰，无冗余文件
  - 零敏感信息泄露，License 文件合规
  - 社区文件齐全（Issue/PR 模板、贡献指南）

## Day 2：README 重构（Mermaid 架构/快速启动/AI 声明）

- **目标**：编写专业 README，包含架构图、快速启动命令、API 文档与 AI 辅助声明。
- **实操**：
  1. 编写项目简介：一句话描述 + 核心亮点（3-5 个 Bullet）。
  2. 绘制 Mermaid 架构图：展示系统组件关系（前端/后端/AI 引擎/数据库/缓存）。
  3. 编写快速启动：环境要求 → 安装依赖 → 配置环境变量 → 一键启动。
  4. 编写 API 文档概览：核心端点 + 请求/响应示例 + Swagger 链接。
  5. 添加 AI 辅助声明：说明项目中 AI 辅助比例与使用工具。
  6. 添加 Badges：CI 状态、Coverage、License、Python 版本、Docker Pulls。
- **Prompt 模板**：

```md
重构项目 README，要求：

1. 项目简介 + Badges：
   [![CI](https://github.com/user/repo/actions/workflows/ci.yml/badge.svg)](...)
   [![Coverage](https://codecov.io/...)](...)
   [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](...)
   [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](...)

2. Mermaid 架构图：
   ```mermaid
   graph TD
       subgraph Frontend
           Web[React H5] -->|HTTP/SSE| Gateway[API Gateway]
           MP[Taro 小程序] -->|HTTP/SSE| Gateway
       end
       subgraph Backend
           Gateway --> Router[Agent Router]
           Router --> Base[Base Model]
           Router --> Finetuned[Finetuned Model]
           Base --> vLLM[vLLM Server]
           Finetuned --> vLLM
       end
       subgraph Data
           Router --> PG[(PostgreSQL)]
           Router --> Redis[(Redis Cache)]
       end
   ```

3. 快速启动（3 步）：
   ```bash
   # Step 1: Clone + Install
   git clone https://github.com/user/repo.git && cd repo
   cp .env.example .env  # 填入 API Keys

   # Step 2: Start services
   docker-compose up -d

   # Step 3: Verify
   curl http://localhost:8000/healthz
   # 访问 http://localhost:8000/docs 查看 API 文档
   ```

4. AI 辅助声明：
   > 本项目使用 AI 辅助开发（Cursor + Claude）。
   > - 代码生成辅助比例：约 60%
   > - AI 辅助模块：API 路由、测试生成、文档编写
   > - 人工决策：架构设计、安全审查、核心 Agent 逻辑
   > - 所有 AI 生成代码均经过人工 Review
```

- **验收**：
  - README 包含架构图 + 快速启动 + API 概览 + AI 声明
  - Badges 齐全，一键复制可启动
  - 新用户 5 分钟内理解项目并能跑起来

## Day 3：技术博客 #1（Agent 多智能体协作落地）

- **目标**：撰写 LangGraph 多 Agent 协作的技术博客，分享实战经验。
- **实操**：
  1. 选题：基于 Week 4-5 实战经验，聚焦 LangGraph 多 Agent 或 vLLM 部署主题。
  2. 结构设计：背景 → 问题 → 方案 → 实现 → 效果 → 总结。
  3. 代码示例：包含可直接运行的代码片段（GitHub Gist 或仓库链接）。
  4. 图表辅助：流程图、架构图、性能对比图。
  5. 发布平台：掘金/知乎/Medium/Dev.to/个人博客。
- **Prompt 模板**：

```md
撰写 LangGraph 多 Agent 协作实战博客，要求：

1. 结构：
   ## 背景
   - 单 Agent 局限性：单一模型无法处理复杂多步骤任务
   - 为什么需要多 Agent 协作

   ## 架构设计
   - Supervisor-Worker 模式（Mermaid 流程图）
   - 角色划分：Supervisor（任务分配）、Researcher（搜索）、Coder（写代码）、Reviewer（审查）

   ## 关键实现
   - StateGraph 定义 & 状态管理
   - Agent 间通信（SharedState vs Message Passing）
   - 条件路由 & 循环控制（防死循环，max_iterations=10）

   ## 实战案例
   - 场景："开发一个用户反馈分析系统"
   - 协作流程：Supervisor → Coder（写 FastAPI）→ Reviewer（审查）→ Coder（修正）→ 交付
   - 代码片段（GitHub Gist）

   ## 效果对比
   - 单 Agent vs 多 Agent：任务完成率 65% → 92%
   - 代码质量：Review issue 减少 40%

   ## 踩坑记录
   - 死循环问题与解决方案
   - Token 消耗优化策略
   - 状态一致性处理

   ## 总结
   - 适合场景 vs 不适合场景
   - 下一步：Human-in-the-Loop 集成

2. 发布 Checklist：
   - [ ] 代码可运行，Gist/Repo 链接有效
   - [ ] Mermaid 流程图正确渲染
   - [ ] SEO 标题 + 标签（LangGraph, Agent, Multi-Agent）
   - [ ] 社交媒体推广（Twitter/LinkedIn/微信群）
```

- **验收**：
  - 博客发布，结构完整 > 2000 字
  - 代码示例可运行，图表清晰
  - 阅读量 ≥ 500（首周）或收到 ≥ 3 条评论

## Day 4：技术博客 #2（vLLM 部署与推理加速）

- **目标**：撰写 vLLM 部署与性能优化的技术博客，分享量化推理实战经验。
- **实操**：
  1. 选题：基于 Week 4 实践，聚焦 vLLM 生产部署、KV Cache 调优或量化加速。
  2. 结构设计：动机 → 方案对比 → 详细步骤 → Benchmark → 踩坑。
  3. 数据支撑：附 Benchmark 数据（延迟/吞吐/显存对比表格）。
  4. 发布平台：同上。
- **Prompt 模板**：

```md
撰写 vLLM 生产部署与推理加速实战博客，要求：

1. 结构：
   ## 动机
   - 业务场景：AI SaaS 需要低延迟、高并发推理
   - 传统方案痛点：Hugging Face Transformers 推理慢、显存高

   ## 方案对比
   | 方案 | QPS | P95 Latency | GPU VRAM | 部署复杂度 |
   |------|-----|-------------|----------|-----------|
   | Transformers (FP16) | 5 | 8s | 16GB | 低 |
   | vLLM (FP16) | 50 | 1.2s | 14GB | 中 |
   | vLLM + AWQ (INT4) | 120 | 0.6s | 5GB | 中 |

   ## 部署步骤
   ```bash
   # 1. 安装 vLLM
   pip install vllm

   # 2. 启动服务
   vllm serve Qwen/Qwen2.5-7B-Instruct \
     --host 0.0.0.0 --port 8000 \
     --gpu-memory-utilization 0.9 \
     --max-model-len 4096 \
     --enable-chunked-prefill

   # 3. 验证
   curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{...}'
   ```

   ## KV Cache 调优
   - block_size 选择：16 vs 32 的影响
   - gpu_memory_utilization：0.85 vs 0.90 vs 0.95 的 OOM 边界
   - max_num_seqs 与并发能力
   - 最终配置 & 性能数据

   ## AWQ 量化加速
   - 量化流程：calibration → quantize → verify
   - 量化效果：显存 -70%，吞吐 +2.4x，PPL +3%（可接受）
   - 注意事项：校准数据集选择影响精度

   ## 常见问题
   - OOM：降低 gpu_memory_utilization 或 max_num_seqs
   - SSE 断流：检查 Nginx proxy_buffering off
   - 长文本延迟高：enable chunked_prefill + increase block_size

2. 发布 Checklist：
   - [ ] Benchmark 数据可复现
   - [ ] 启动命令可直接复制运行
   - [ ] 性能对比表格完整
```

- **验收**：
  - 博客发布，结构完整 > 2000 字
  - Benchmark 数据详实，命令可运行

## Day 5：开源 PR 提交（LangChain/vLLM 文档或 Bug 修复）

- **目标**：向知名开源项目提交 PR，积累开源贡献记录。
- **实操**：
  1. 在 LangChain / vLLM / llama.cpp / Taro 等项目 Issues 中寻找 `good first issue`。
  2. Fork 项目 → 本地修复（文档/小 Bug/Type Hint）→ 提交 PR。
  3. PR 描述：问题描述 → 修复方案 → 测试验证 → 关联 Issue。
  4. 跟进 Review 反馈，及时修改。
  5. 记录贡献：PR 链接、学习收获。
- **Prompt 模板**：

```md
指导开源 PR 提交流程，要求：

1. 寻找适合的 Issue：
   - 标签筛选：good first issue / help wanted / documentation
   - 推荐项目：LangChain, vLLM, Taro, llama.cpp, FastAPI
   - 适合首次贡献的类型：
     · 文档修正（拼写/示例/链接）
     · Type Hint 补全
     · 测试补充（edge case）
     · 小 Bug 修复（< 20 行变更）

2. PR 提交流程：
   ```bash
   # Fork & Clone
   gh repo fork langchain-ai/langchain --clone
   cd langchain

   # 创建分支
   git checkout -b fix/typo-in-agent-docs

   # 修改 → 测试 → 提交
   git add . && git commit -m "docs: fix typo in Agent documentation"
   git push origin fix/typo-in-agent-docs

   # 创建 PR
   gh pr create --title "docs: fix typo in Agent documentation" --body "..."
   ```

3. PR 描述模板：
   ## Description
   - Fixed typo in Agent documentation: "recieve" → "receive"
   - File: docs/docs/modules/agents/

   ## Testing
   - N/A (documentation only)

   ## Related Issues
   - None

   ## Checklist
   - [x] Lint and tests pass

4. Review 应对：
   - 及时回应 Review 评论（24h 内）
   - 认真修改，感谢 Reviewers
   - 若被拒，理解原因，积累经验
```

- **验收**：
  - ≥ 1 个 PR 提交，进入 Review 或已 Merge
  - 贡献记录可查（GitHub Contributions）

## Day 6：3 分钟 Demo 视频录制

- **目标**：录制高质量项目 Demo 视频，展示核心功能与技术亮点。
- **实操**：
  1. 编写脚本大纲（1 页）：开场 → 核心功能演示 → 技术亮点 → 结尾 CTA。
  2. 录制：使用 OBS Studio / QuickTime 录制屏幕 + 画外音。
  3. 编辑：剪映 / iMovie / Davinci Resolve 剪辑至 3 分钟，添加字幕、高亮标注。
  4. 导出 1080p MP4，上传 YouTube / Bilibili，嵌入 README。
  5. 视频封面设计（Canva 快速生成）。
- **Prompt 模板**：

```md
编写 3 分钟产品 Demo 视频脚本与录制指南，要求：

1. 脚本大纲（3 分钟）：
   - 0:00-0:15 开场：一句话产品介绍 + 技术栈
     "这是一个 AI-Native SaaS，支持多 Agent 协作与领域模型热切换..."

   - 0:15-1:00 核心功能 Demo：
     · 发送领域问题 → Agent 自动路由至微调模型
     · 展示 SSE 流式响应 & Markdown 渲染
     · Agent 调用 Tool（查询 DB/搜索）

   - 1:00-1:45 技术亮点：
     · 快速切换模型：展示 Agent Tools 热切换
     · W&B 面板：展示训练 Loss 曲线与 QA 提升
     · vLLM Dashboard：实时 QPS/延迟监控

   - 1:45-2:30 架构展示：
     · Mermaid 架构图讲解
     · 技术栈介绍：FastAPI + LangGraph + vLLM + Taro

   - 2:30-3:00 结尾 CTA：
     · "完整代码已开源，欢迎 Star & Follow"
     · GitHub + Blog 链接展示

2. 录制配置 (OBS)：
   - Scene 1: 浏览器 (Demo) + 画外音
   - Scene 2: VS Code (代码展示)
   - Scene 3: Grafana Dashboard (监控)
   - 分辨率：1920×1080，帧率 30fps
   - 音频：外接麦克风，降噪

3. 后期制作 Checklist：
   - [ ] 剪辑至 3:00 ± 15s
   - [ ] 中英双语字幕（SRT 格式）+ 硬字幕嵌入
   - [ ] 高亮标注：关键点击位置（红色圆圈/箭头）
   - [ ] 封面图 (Canva): 项目图标 + "AI-Native SaaS Demo"
   - [ ] BGM 背景音（淡入淡出）
```

- **验收**：
  - 3 分钟视频完成，画质 1080p
  - 核心功能演示清晰，字幕/高亮齐全
  - 上传 YouTube/Bilibili，嵌入 README

## Day 7：个人 Portfolio 页面搭建

- **目标**：搭建个人技术 Portfolio 页面，展示项目、博客、GitHub 贡献。
- **实操**：
  1. 搭建 Portfolio 站点：GitHub Pages + Jekyll/Hexo 或直接使用 `next.js` 静态导出。
  2. 页面板块：About Me → Projects → Blog → GitHub Stats → Contact。
  3. 项目展示：Week 1-12 核心项目，附截图 + GitHub 链接 + Live Demo 链接。
  4. GitHub Profile README：添加个人简介、技能标签、GitHub Stats、本周动态。
  5. 优化 SEO：标题/描述/关键词配置，提交至 Google/Bing 索引。
- **Prompt 模板**：

```md
搭建个人技术 Portfolio 页面，要求：

1. 页面结构 (单页设计)：
   - Hero Section：头像 + 姓名 + 一句话定位 + Social Links (GitHub/LinkedIn/Blog)
   - About Me：简介（3 句）+ 技术栈 Tag Cloud (Python/FastAPI/vLLM/LangGraph/Taro)
   - Projects Grid（3-4 个项目卡片）：
     · 项目截图/GIF
     · 标题 + 一句话描述
     · Tech Stack 标签
     · [Live Demo] [GitHub] 按钮
   - Blog：最新 3 篇文章卡片（标题/日期/摘要）→ 查看全部
   - GitHub Stats：贡献热力图 (ghchart) + Stars/PRs 统计
   - Contact：Email + LinkedIn + WeChat(可选)

2. GitHub Profile README 增强：
   ```markdown
   ## Hi, I'm [Name] 👋
   > AI-Native FullStack Developer | Open Source Contributor

   ### Tech Stack
   ![Python](https://img.shields.io/badge/-Python-3776AB)
   ![FastAPI](https://img.shields.io/badge/-FastAPI-009688)
   ![LangChain](https://img.shields.io/badge/-LangChain-1C3B3B)
   ![vLLM](https://img.shields.io/badge/-vLLM-FF6F00)
   ![Taro](https://img.shields.io/badge/-Taro-FF6B81)

   ### Weekly Highlights
   - 🔥 Published: "LangGraph Multi-Agent in Production"
   - 🚀 Merged PR: vLLM docs fix
   - 📊 Open Source: `ai-saas-platform` reaching 50 stars

   ![GitHub Stats](https://github-readme-stats.vercel.app/api?username=xxx&show_icons=true)
   ```

3. 部署选项：
   - 推荐：Vercel (免费 + 自动 HTTPS + CDN)
   - 备选：GitHub Pages (免费 + 简单配置)
   - 域名：自定义域名 (Namecheap 约 $10/年)

4. SEO Checklist：
   - [ ] `<title>` + `<meta description>` 完善
   - [ ] Open Graph tags（社交分享预览）
   - [ ] sitemap.xml + robots.txt
   - [ ] Google Search Console + Bing Webmaster 提交索引
```

- **验收**：
  - Portfolio 页面在线可访问
  - 项目展示 + 博客 + GitHub Stats 完整
  - GitHub Profile README 增强

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 目录结构清晰；零敏感信息泄露；License 合规；社区文件齐全 |
| D2 | README 含 Mermaid 架构图 + 一键启动 + Badges + AI 声明 |
| D3 | 博客 > 2000 字，代码可运行，图表清晰，平台发布 |
| D4 | 博客 > 2000 字，Benchmark 数据详实，Benchmark 数据支撑 |
| D5 | ≥ 1 个 PR 提交，进入 Review 或已 Merge |
| D6 | 3 分钟视频（1080p），字幕/高亮齐全，平台上传 |
| D7 | Portfolio 页面上线，GitHub Profile 增强，SEO 配置 |

## 最终验收标准

- README 专业完整，Mermaid 架构 + 一键启动 + AI 声明，Star/Fork 友好
- 2 篇技术博客发布，≥ 1 个开源 PR 进入 Review
- 3 分钟 Demo 视频流畅，技术亮点突出
- 个人 Portfolio 页面上线，项目/博客/GitHub 贡献完整展示

## 高频 Prompt 模板

1. **仓库审计与合规 Prompt**
   - 目录结构审计 + License 选择
   - 敏感信息扫描（git-secrets/trufflehog）
   - Issue/PR 模板 + 贡献指南

2. **README 重构 Prompt**
   - Mermaid 架构图 + Badges 配置
   - 一键启动脚本 + API 概览
   - AI 辅助声明（比例/工具/边界）

3. **技术博客撰写 Prompt**
   - 背景 → 问题 → 方案 → 实现 → 效果 结构
   - Mermaid 图 + Benchmark 表格 + 代码片段
   - SEO 标签 + 社交推广 Checklist

4. **vLLM 部署实战博客 Prompt**
   - 方案对比表格（QPS/延迟/显存）
   - 部署配置详解 + KV Cache 调优
   - AWQ 量化效果 + 踩坑记录

5. **开源 PR 提交指南 Prompt**
   - good first issue 筛选策略
   - Fork → PR → Review 全流程命令
   - PR 描述模板 + Review 应对

6. **3 分钟 Demo 录制 Prompt**
   - 脚本时间线（开场/功能/亮点/结尾）
   - OBS 场景 + 后期制作 Checklist
   - 封面设计 + 字幕/高亮

7. **Portfolio 页面搭建 Prompt**
   - 单页结构（Hero/Projects/Blog/Stats）
   - GitHub Profile README 增强
   - 部署选项 + SEO Checklist

## 动态调整建议

- **无开源贡献经验**：Day 5 优先文档类 PR（门槛低、易通过），vLLM/LangChain 文档 Issue 较多。
- **不擅长视频制作**：Day 6 可简化为 GIF 截图串联 + 字幕，降低剪辑复杂度。
- **已有 Portfolio**：Day 7 聚焦内容更新（新项目 + 新博客），不必重新搭建。
- **写作能力强 / 技术弱**：Day 3-4 博客多花时间打磨文章质量，Day 5 开源 PR 可降级为 Star/Fork 学习。
- **想冲击海外市场**：博客中英双语发布 Medium/Dev.to，Portfolio 和 README 中英双语。

## 第 7 天自测清单

- [ ] 仓库审计完成，敏感信息清理，License + 社区文件齐全
- [ ] README 重构，Mermaid 架构图 + 一键启动 + Badges + AI 声明
- [ ] 2 篇技术博客发布（> 2000 字/篇），代码可运行
- [ ] ≥ 1 个开源 PR 提交，进入 Review 或已 Merge
- [ ] 3 分钟 Demo 视频（1080p），字幕/高亮齐全，平台上传
- [ ] Portfolio 页面上线，GitHub Profile README 增强
- [ ] 仓库包含：优化后源码、README、博客文章、视频链接、PR 记录
- [ ] 能清晰口述项目核心价值、技术亮点与开源贡献方法论
