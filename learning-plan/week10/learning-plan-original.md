# Week 10: AI-Native 工作流标准化

## 🎯 目标
沉淀团队级 Prompt 工程库与自动化审查流程。掌握高级上下文工程、AI 辅助 PR 审查、Prompt 版本管理与 A/B 测试、Token 成本追踪与模型路由核算、团队规范文档编写、AI Coding ROI 基准测试到内部 Workshop 反馈迭代，最终交付可复用、可度量的 AI-Native 研发工作流。

---

## Day 1：Context Engineering 进阶（分层提示/防幻觉）

- **目标**：掌握结构化上下文注入与防幻觉机制，提升复杂任务的指令遵循率与事实准确性。
- **实操**：
  1. 设计分层 Prompt 架构：`System（角色/约束）→ Context（知识与记忆）→ Task（具体指令）→ Output（格式/校验）`。
  2. 实现防幻觉策略：强制引用来源（`[source]`）、未知声明机制、自我验证步骤（Self-Correction Loop）。
  3. 构建 Prompt Chain：复杂任务拆分为多步子任务，每步输出可验证中间结果。
  4. 实现 Prompt 注入防护：角色强化、参数化模板、用户输入隔离。
  5. 构造对抗测试集：模糊指令、矛盾前提、越权请求，验证 Prompt 鲁棒性。
  6. 编写 Context Engineering Playbook：分层架构模板、防幻觉策略清单、常见陷阱。
- **Prompt 模板**：

```md
构建高级分层上下文工程模板与防幻觉流水线，要求：

1. 严格四层结构：Role/System → Knowledge/Context → Task/Instruction → Output/Validation
2. Self-Correction 循环：生成后自动执行"事实核对/逻辑一致性/格式校验"三步自检，失败则触发重试
3. 防幻觉机制：强制标注引用来源（如 [Doc#3]），未知问题输出标准化占位符，禁用过度推断
4. 动态变量注入：支持 YAML/JSON 上下文映射，运行时替换占位符，保留原始 Prompt 可读性
5. 提供对抗测试报告：模糊/矛盾/越权场景下的拦截率、自检成功率、幻觉下降比例
```

- **验收**：
  - ✅ 分层结构清晰，动态变量注入 100% 准确
  - ✅ 防幻觉机制生效，事实错误率下降 > 30%
  - ✅ 自我验证步拦截率 > 85%，重试逻辑稳定
  - ✅ 对抗测试报告完整，鲁棒性指标可量化

## Day 2：自动化 PR Review（Cursor/Cline 审查模板）

- **目标**：将 AI 深度集成至代码审查流，实现规范检查、代码质量与安全审计自动化。
- **实操**：
  1. 编写 PR Review Prompt 模板：代码风格、类型安全、性能隐患、安全漏洞四维度审查。
  2. 配置 Cursor/Cline Rules（`.cursorrules`/`.clinerules`）：定义项目级编码规范与安全红线。
  3. 集成 GitHub Actions：PR 创建/更新时触发 AI Review，生成结构化评论（文件路径、行号、严重等级、修复建议）。
  4. 实现审查分级：MUST FIX（阻断合并）/ SHOULD FIX（建议修复）/ NICE TO HAVE（可选优化）。
  5. 设置人工复核门控：AI 标记 HIGH 问题需人工确认后方可合并。
  6. 统计审查覆盖率与采纳率，持续优化 Prompt 模板。
- **Prompt 模板**：

```md
实现 Cursor/Cline 自动化 PR 审查与 GitHub 集成流水线，要求：

1. 审查维度覆盖：代码风格、异常处理、安全漏洞（SQL 注入/XSS/密钥泄露）、性能反模式（N+1 查询/同步阻塞）、架构一致性
2. 输出结构化评论：JSON 格式包含 file/line/severity（LOW/MED/HIGH）/suggestion/fix_command
3. GitHub Actions 触发：PR open/sync 自动调用 AI，评论精准打点，支持 /fix 自动生成 Patch
4. 人工门控：HIGH 问题阻塞合并（Require Review），MED/LOW 仅提示，支持一键忽略或采纳
5. 性能要求：单次审查 < 90s，不重复评论已修复问题，支持 diff 增量审查
6. 提供审查质量报告：误报率、采纳率、平均修复时间、拦截的高危 Issue 数量
```

- **验收**：
  - ✅ 审查覆盖团队 80% 核心规范，误报率 < 10%
  - ✅ GitHub 评论精准定位，`/fix` 命令可用
  - ✅ 高危问题拦截率 100%，人工门控生效
  - ✅ 审查耗时 < 90s，增量 diff 审查稳定

## Day 3：Prompt 版本库（分类/A/B 测试）

- **目标**：建立 Git 驱动的 Prompt 资产库，支持分类检索、版本回滚与数据驱动的 A/B 测试。
- **实操**：
  1. 设计 Prompt 仓库结构：按 `domain/task/model` 分层，YAML 格式存储模板、变量、元数据（作者/版本/适用模型）。
  2. 实现版本控制：语义化标签（`v1.2.0`），变更日志（Changelog），支持 `git revert` 快速回滚。
  3. 构建 A/B 测试框架：路由层按用户/流量比例分发 Prompt 变体，记录成功率/Token 消耗/延迟/人工评分。
  4. 自动化优胜判定：基于加权指标（质量 60% + 成本 20% + 延迟 20%）自动推荐 Winner，写入 `best_prompt.yaml`。
  5. 实现 Prompt Registry 类：`registry.get(name, version="latest")`、`registry.compare(a, b)`。
- **Prompt 模板**：

```md
构建 Git 驱动的 Prompt 版本库与 A/B 测试框架，要求：

1. 仓库结构：按 domain/task/model 分类，YAML 模板含 variables/version/metadata/fallback
2. 版本管理：语义化标签，自动 Changelog 生成，支持 git revert 与 diff 可视化对比
3. A/B 路由：流量比例可配（如 50/50），记录 completion_rate/token_cost/latency/human_score
4. 优胜判定算法：加权评分模型（质量 60%/成本 20%/延迟 20%），置信度 > 90% 自动标记 winner
5. 提供测试看板：实时指标曲线、变体对比表、回滚一键触发脚本
6. 兼容 CI：PR 提交 Prompt 变更自动触发 lint + dry-run 测试，拦截语法错误
```

- **验收**：
  - ✅ Prompt 仓库结构清晰，YAML 校验 100% 通过
  - ✅ A/B 测试框架跑通，流量分发与指标采集准确
  - ✅ 优胜判定逻辑生效，Winner 自动落盘
  - ✅ 版本回滚 < 10s，CI 拦截无效 Prompt 变更

## Day 4：Token 成本追踪与模型路由核算

- **目标**：实现细粒度 Token/成本监控，构建成本感知的智能路由与优化策略。
- **实操**：
  1. 实现 Token 用量追踪中间件：拦截所有 LLM 调用，解析 `usage.prompt_tokens/completion_tokens/total_tokens`。
  2. 对接实时计费表（按模型/区域），计算单次请求成本，写入时序数据库（Prometheus/ClickHouse）。
  3. 按维度统计分析：按用户/会话/日期/模型/功能模块聚合 Token 消耗与成本。
  4. 实现成本告警：单用户日消耗 > $5、月消耗 > $50 触发通知。
  5. 模型路由 ROI 分析：对比 GPT-4 vs GPT-4o-mini vs 本地模型的 cost per task + quality。
  6. 输出成本优化建议报告：高消耗路径识别、模型降级机会、缓存复用建议。
- **Prompt 模板**：

```md
开发 Token 成本追踪中间件与智能路由核算系统，要求：

1. 拦截层解析 usage 字段，实时计算单次成本（支持多模型定价表热加载）
2. 时序指标上报：token_input/token_output/cost_usd/model/user_id/project
3. 成本看板：按维度聚合（团队/模型/日），展示预算消耗率、Top 消耗接口、异常突增告警
4. 成本路由：基于任务复杂度评分（规则/LLM 评估）自动选择性价比最优模型
5. 预算控制：单用户/日/月阈值拦截，触发 fallback 至轻量模型或缓存响应
6. 输出月度成本优化报告：路由节省比例、冗余 Token 清理建议、模型替换收益测算
```

- **验收**：
  - ✅ Token 解析 100% 准确，成本核算误差 < 2%
  - ✅ 成本看板实时刷新，维度聚合流畅
  - ✅ 成本路由生效，同等质量下成本下降 > 20%
  - ✅ 预算拦截准确，降级策略无业务中断

## Day 5：团队规范文档（分支策略/AI 使用边界）

- **目标**：制定标准化 AI 研发规范，明确分支策略、人机协同边界与数据合规红线。
- **实操**：
  1. 编写 `AI-CODING-GUIDELINES.md`：定义适用场景（模板代码/重构/测试）、禁用场景（核心算法/涉密逻辑）。
  2. 编写 Git 分支策略：`feat/ai-assisted` → `pr-review-ai` → `main`，AI 生成代码必须人工 Review 与签名。
  3. 编写代码质量标准：测试覆盖率 ≥ 80%、类型检查 strict、Lint 零 WARNING/ERROR、安全审查清单。
  4. 编写 AI-Native 工作流文档：从需求 → Prompt → 生成 → 审核 → 测试的完整流程。
  5. 设定数据安全红线：禁止上传客户 PII、内部密钥、未脱敏业务数据至公有云 API。
  6. 设计合规检查清单：PR 模板嵌入 `AI-Usage-Checklist`，CI 自动扫描敏感词与违规 Prompt 调用。
- **Prompt 模板**：

```md
生成团队 AI-Native 研发规范与分支合规策略，要求：

1. 明确使用边界：允许/禁用场景清单，人机协同责任划分（AI 辅助 vs 人类决策）
2. 分支策略：feat/ai-assisted → ai-pr-review → main，强制人工复核与 Commit 签名
3. 数据安全红线：PII/密钥/核心资产禁止外发，强制本地路由或脱敏代理
4. CI 合规扫描：PR 模板内置 checklist，自动拦截未声明 AI 使用或敏感数据调用
5. 提供 Onboarding 指南：新成员 1 小时上手流程、IDE 配置、规范签署模板
6. 版本化管理：Markdown 结构，PR 审核发布，季度 Review 迭代机制
```

- **验收**：
  - ✅ 规范文档完整，边界清晰可执行
  - ✅ 分支策略落地，AI 代码 100% 人工复核
  - ✅ 数据安全红线明确，CI 拦截准确
  - ✅ Onboarding 指南可用，新人 1 小时内可合规编码

## Day 6：AI Coding ROI 基准测试

- **目标**：量化 AI 对研发效能、质量与成本的影响，建立可复用的 ROI 评估基线。
- **实操**：
  1. 定义 ROI 指标：PR 周期缩短率、Bug 逃逸率下降、代码行数/小时、Token 成本/功能点、人工 Review 时间占比。
  2. 设计 A/B 对照实验：相同任务分别人工编写 vs AI 辅助编写，控制复杂度与经验水平。
  3. 采集真实数据：Jira 工时、Git 提交频率、SonarQube 质量门禁、LLM 计费账单。
  4. 统计分析：使用 t-test 验证显著性，计算 ROI = (收益 - 成本)/成本，输出置信区间。
  5. 输出 ROI 基准报告：效能对比雷达图、成本收益散点、Actionable 洞察。
- **Prompt 模板**：

```md
构建 AI 研发 ROI 基准测试框架与数据分析流水线，要求：

1. 指标定义：pr_cycle_time、bug_escape_rate、lines_per_hour、cost_per_feature、review_time_pct
2. 实验设计：A/B 组对照，控制复杂度与经验变量，最小样本量计算（Power > 0.8）
3. 数据接入：自动拉取 Jira/Git/SonarQube/计费账单，清洗异常值与缺失值
4. 统计分析：t-test/ANOVA 验证显著性，计算 ROI = (收益 - 成本)/成本，输出置信区间
5. 生成可视化报告：效能对比雷达图、成本收益散点、显著性标记、Actionable 洞察
6. 提供基线模板：团队可替换数据源一键重算，支持季度趋势追踪
```

- **验收**：
  - ✅ 实验设计严谨，样本量与显著性达标
  - ✅ 数据自动采集清洗，零人工干预
  - ✅ ROI 计算准确，效率提升 ≥ 30%
  - ✅ 报告可视化完整，可直接用于管理层汇报

## Day 7：内部 Workshop + 反馈迭代

- **目标**：组织团队实战培训，收集一线反馈，闭环优化工作流并正式发布 v1.0 标准。
- **实操**：
  1. 策划 Workshop 议程（2h）：30min 理念分享 → 45min Live Coding Demo → 30min 团队讨论 → 15min 反馈收集。
  2. 设计动手实验：分组完成指定任务，使用 Prompt 库提交 PR，对比效率与质量差异。
  3. 收集反馈问卷：覆盖易用性、痛点、缺失能力、培训需求，量化 NPS 与改进优先级。
  4. 迭代工作流：根据反馈修订 Prompt 模板、审查标准、团队规范。
  5. 发布 v1.0：Release Notes 模板化，Adoption Plan 明确试点范围、推广节奏、Support 渠道。
- **Prompt 模板**：

```md
设计 AI-Native Workshop 实战演练与反馈迭代流水线，要求：

1. 议程规划：理论 30min + 实战 60min + 复盘 30min，覆盖 Prompt/PR/Cost/Rules 核心模块
2. 动手实验：分组任务（如"用 v2.1 Prompt 优化接口 + 提交 PR 触发 AI Review"），提供评分卡
3. 反馈收集：量化问卷（NPS/痛点/需求），开放白板墙收集定性建议，自动聚合分析
4. 迭代闭环：Top 3 需求 48h 内落地，更新 Prompt 库/CI 规则/文档，生成 Changelog
5. 发布 v1.0：Release Notes 模板化，Adoption Plan 明确试点范围、推广节奏、Support 渠道
6. 提供培训资产包：录屏、讲义、实验脚本、FAQ，支持异步学习与新人 Onboarding
```

- **验收**：
  - ✅ Workshop 成功举办，参与率 > 80%
  - ✅ 反馈收集完整，NPS ≥ 7
  - ✅ Top 3 需求 48h 内闭环，文档/规则同步更新
  - ✅ v1.0 正式发布，Adoption Plan 清晰可执行

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 分层 Prompt 结构清晰；防幻觉机制生效；自我验证拦截率 > 85%；Playbook 完成 |
| D2 | 审查覆盖 80% 规范；GitHub 评论精准定位；高危拦截 100%；耗时 < 90s |
| D3 | Prompt 仓库结构完整；A/B 框架跑通；Winner 自动判定；版本回滚 < 10s |
| D4 | Token 解析 100% 准确；成本核算误差 < 2%；成本路由降本 > 20%；预算拦截生效 |
| D5 | 规范文档完整可执行；AI 代码 100% 人工复核；数据安全红线明确；CI 合规拦截准确 |
| D6 | 实验设计显著性达标；数据自动采集；ROI 计算准确；效率提升 ≥ 30% |
| D7 | Workshop 参与率 > 80%；NPS ≥ 7；Top 3 需求 48h 闭环；v1.0 发布 |

## 最终验收标准

- ✅ Prompt 库支持 Git 版本管理、分类检索与 A/B 测试，优胜版本自动落盘
- ✅ 自动化 PR 审查覆盖团队 80% 规范，高危问题拦截率 100%，人工门控生效
- ✅ Token 成本追踪误差 < 2%，成本感知路由降本 > 20%，预算超限自动降级
- ✅ AI 研发规范文档完整发布，分支策略与数据合规红线 100% 团队签署执行
- ✅ ROI 基准测试完成，输出显著性结论与管理层可量化报告
- ✅ 内部 Workshop 成功举办，反馈闭环落地，v1.0 工作流标准正式发布

## 高频 Prompt 模板

1. **分层上下文工程与防幻觉 Prompt**
   - System/Context/Instruction/Output 四层架构
   - 强制引用、未知声明、Self-Correction 循环
   - 动态变量注入与对抗测试报告生成

2. **Cursor/Cline 自动化 PR 审查 Prompt**
   - 规范/安全/性能多维审查矩阵
   - 结构化 JSON 评论与 `/fix` 自动生成
   - GitHub Actions 集成与人工门控策略

3. **Prompt 版本库与 A/B 测试 Prompt**
   - Git/YAML 结构化存储与语义化版本
   - 流量分流、指标采集、加权优胜判定
   - CI 拦截与一键回滚机制

4. **Token 成本追踪与智能路由 Prompt**
   - Usage 解析、实时计费、时序指标上报
   - 多维度成本看板与预算阈值拦截
   - 成本感知模型路由与优化报告

5. **团队 AI 使用规范与分支策略 Prompt**
   - 适用/禁用场景清单与责任划分
   - Git 分支流与 Commit 签名要求
   - 数据红线与 CI 合规扫描 Checklist

6. **AI Coding ROI 基准测试 Prompt**
   - 指标定义、A/B 实验设计、显著性检验
   - 多源数据自动接入与清洗
   - ROI 计算公式、置信区间与可视化报告

7. **Workshop 实战与反馈迭代 Prompt**
   - 议程规划、分组实验、评分卡设计
   - 问卷回收、NPS 计算、需求聚合
   - v1.0 Release Notes 与 Adoption Plan 模板

## 动态调整建议

- **团队 AI 基础薄弱**：
  - D1/D2 优先跑通"防幻觉模板 + Cursor 基础审查"，暂不接入复杂 A/B 与成本路由。
- **无内部计费/监控基建**：
  - D4 先用 CSV + 简单脚本手动核算成本，跑通逻辑后再对接 Prometheus/ClickHouse。
- **PR 审查误报率高**：
  - D2 调整 Prompt 温度（`temperature=0.2`），引入 `.cursorrules` 白名单文件/目录，跳过非核心模块。
- **ROI 实验难控制变量**：
  - D6 改为"前后对比"（Pre-AI vs Post-AI），使用相同任务池与相同开发者。
- **推行阻力大**：
  - D7 Workshop 增加"老带新"实战环节，设置"早期采用者奖励"提升参与意愿。
- **合规/法务要求严格**：
  - D5 前置法务审核，增加"数据出境/版权归属/AI 生成内容声明"条款。

## 第 7 天自测清单

- [ ] 分层 Prompt 模板库结构化落地，防幻觉与自检机制稳定运行
- [ ] GitHub PR 自动审查触发正常，高危问题拦截率 100%，`/fix` 命令可用
- [ ] Prompt 版本库支持 YAML 分类、A/B 分流与 Winner 自动判定，回滚顺畅
- [ ] Token 成本追踪准确，路由降本 > 20%，预算拦截无业务中断
- [ ] 团队规范文档签署生效，分支策略与数据红线 CI 自动校验
- [ ] ROI 基准测试完成，输出显著性结论与管理层可视化报告
- [ ] Workshop 成功举办，反馈闭环落地，v1.0 标准正式发布
- [ ] 仓库包含：Prompt 模板库、PR Review 规则、A/B 框架、成本追踪脚本、规范文档、ROI 分析脚本、Workshop 资产包
- [ ] 能清晰口述：Context Engineering 架构、AI 审查门控逻辑、Prompt 版本化机制、成本路由策略、合规边界与 ROI 评估方法论
