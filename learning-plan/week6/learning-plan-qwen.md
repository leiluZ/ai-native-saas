# Week 6: 小程序端接入与 UI/UX 精细化

## 🎯 目标
完成微信小程序接入，实现跨端同步与高还原度 UI。掌握现代跨端工程化、状态持久化、微信核心 API、设计系统落地、AI 辅助代码生成与生产级发布流程。

---

## Day 1：Taro/Uniapp 初始化 + 多端构建
- **目标**：掌握跨端框架选型与工程化初始化，实现一套代码多端编译（微信/支付宝/H5）。
- **实操**：
  1. 初始化 `Taro` (Vue/React) 或 `UniApp` 项目，集成 TypeScript、ESLint、Prettier、Husky。
  2. 配置多端环境变量（`.env.development` / `.env.production`），抽离平台差异配置。
  3. 搭建标准目录结构：`src/pages`、`src/components`、`src/stores`、`src/utils`、`src/assets`。
  4. 配置 `postcss-pxtransform` 实现 `px -> rpx/rem` 自动转换，统一设计稿基准（750px）。
  5. 跑通基础路由、页面跳转、底部 TabBar，验证 `npm run dev:weapp` 与 `npm run build:h5` 产物。
- **Prompt 模板**：
```md
编写跨端小程序工程初始化与构建配置，要求：
1. 基于 Taro/UniApp 初始化项目，强制 TypeScript 严格模式
2. 配置 .env 多环境变量管理，支持 dev/test/prod 动态注入
3. 封装统一路由拦截器：页面权限校验、埋点上报、全局 Error Boundary
4. 配置 postcss-pxtransform：750px 设计稿基准，rpx 自动转换，禁用 px-to-rem
5. 支持 weapp/h5/alipay 三端编译脚本，产物按需分包（subpackage）
6. 提供 CI 预检脚本：lint、type-check、build-dry-run 一键通过
```
- **验收**：
  - ✅ 工程一键初始化，TS/ESLint 零报错
  - ✅ 支持 weapp/h5/alipay 多端编译
  - ✅ 路由与 TabBar 渲染正常，跳转无白屏
  - ✅ 主包体积 <2MB，支持分包懒加载

---

## Day 2：Pinia/Zustand 持久化 + 本地缓存策略
- **目标**：掌握跨端状态管理，实现数据持久化、缓存分层与过期淘汰策略。
- **实操**：
  1. 集成 `Pinia` (Vue) 或 `Zustand` (React)，配置基础 Store 与模块化拆分。
  2. 接入持久化插件，底层对接 `wx.setStorageSync` / `localStorage`，处理序列化与反序列化。
  3. 设计缓存分层：内存态 -> Storage 持久层 -> 网络兜底层，配置 TTL 过期时间。
  4. 实现 LRU 淘汰策略：当 Storage 接近上限（微信 10MB）时自动清理低频数据。
  5. 编写缓存一致性校验：弱网/断网场景下读取本地快照，网络恢复后静默同步。
- **Prompt 模板**：
```md
构建跨端状态管理与持久化缓存体系，要求：
1. 集成 Pinia/Zustand，模块按业务域拆分（user, chat, config, cache）
2. 封装持久化插件：自动 sync 到 wx.setStorageSync，支持 TTL 与 LRU 淘汰
3. 设计缓存分层策略：内存优先 -> Storage 兜底 -> 网络刷新
4. 处理微信 Storage 10MB 限制：超限自动清理低频 key，输出存储水位日志
5. 提供缓存健康检查接口：getQuotaUsage(), clearExpired(), forceSync()
6. 兼容 H5/小程序双端 API 差异，无条件编译
```
- **验收**：
  - ✅ 状态跨页面/生命周期保持
  - ✅ 持久化读写正常，支持 TTL 自动过期与 LRU 清理
  - ✅ 存储超限自动降级，无报错
  - ✅ 弱网/断网场景可读取本地快照并静默恢复

---

## Day 3：微信授权/分享/订阅消息 API 接入
- **目标**：掌握微信小程序核心能力接入，实现用户登录、社交分享与消息触达闭环。
- **实操**：
  1. 实现 `wx.login` + `code2Session` 后端交互，获取 `openid`/`session_key`/`unionid`。
  2. 封装 Token 无感刷新机制：拦截 401，静默重试 `login`，更新 Access/Refresh Token。
  3. 接入 `onShareAppMessage` / `onShareTimeline`，配置动态标题、封面图、带参路径。
  4. 实现订阅消息（`requestSubscribeMessage`）授权与发送，处理用户拒收、频次限制与模板更新。
  5. 封装 `@wechat/adapter` 统一适配层，隔离平台 API 差异与权限弹窗逻辑。
- **Prompt 模板**：
```md
实现微信核心能力接入与 Token 无感刷新，要求：
1. 完整 login -> code2Session -> token 发放流程，支持 openid/unionid 绑定
2. 封装 Axios/Request 拦截器：401 自动静默刷新，重试队列不丢失原始请求
3. 配置动态分享卡片：支持 onShareAppMessage/onShareTimeline，参数带 source 追踪
4. 订阅消息管理：授权状态缓存、模板 ID 映射、发送成功/拒收日志上报
5. 平台适配层：统一 wx. 与 web API 差异，权限申请失败降级提示
6. 安全合规：不强制授权，敏感操作按需触发，符合微信审核规范
```
- **验收**：
  - ✅ 授权/登录流程完整，无卡死/白屏
  - ✅ Token 刷新无断点，401 重试成功率 >99%
  - ✅ 分享卡片参数动态生效，带参路径可追踪
  - ✅ 订阅消息授权/发送状态可审计，拒收处理优雅

---

## Day 4：组件库定制 + 暗色/动态主题
- **目标**：构建高可复用业务组件库，实现设计系统（Design Tokens）与暗色模式无缝切换。
- **实操**：
  1. 提取 UI 规范，定义 Design Tokens：CSS Variables / Tailwind Config（颜色、间距、圆角、字体）。
  2. 开发核心业务组件（Button, Card, Input, Dialog, Toast），支持 Props 透传、Slot 扩展与类型提示。
  3. 实现 `prefers-color-scheme` 监听与手动切换逻辑，动态切换 CSS 变量，避免整页重绘。
  4. 处理小程序 CSS 变量兼容性：旧版 Android 降级为 `class` 切换，提供 fallback 方案。
  5. 编写组件文档与使用规范，输出 `storybook` 或静态预览页。
- **Prompt 模板**：
```md
构建跨端设计系统与主题组件库，要求：
1. 定义 Design Tokens：--color-primary, --spacing-md, --radius-lg 等，覆盖 100% 业务样式
2. 开发核心组件：Button/Card/Input/Dialog/Toast，支持 Props/Slots 完整透传
3. 暗色模式：监听 prefers-color-scheme + 手动切换，CSS 变量热更新，零闪烁
4. 小程序兼容：CSS 变量降级策略（class 切换），rpx 适配，禁用不支持属性（如 backdrop-filter）
5. 类型系统：导出 .d.ts 完整 Props 定义，IDE 智能提示
6. 组件预览：生成静态 Storybook/H5 预览页，支持明暗切换演示
```
- **验收**：
  - ✅ 核心组件库封装完成，Props 类型完整
  - ✅ 暗色/亮色切换平滑无闪烁，CSS 变量覆盖 100%
  - ✅ Design Tokens 统一管理，业务样式零硬编码
  - ✅ 组件可独立复用，类型提示与文档完善

---

## Day 5：微交互 (骨架屏/流式动画/虚拟列表)
- **目标**：优化用户体验，实现高性能渲染与流畅的微交互动效。
- **实操**：
  1. 实现页面级/组件级骨架屏（Skeleton），支持动态数据占位与懒加载衔接。
  2. 接入流式渲染（Streaming UI）：模拟 AI 打字机效果，`requestAnimationFrame` 节流更新，避免频繁 `setData`。
  3. 实现虚拟列表（Virtual List）：处理长聊天记录/资讯流，按需渲染可视区域 DOM，控制节点数。
  4. 性能优化：`will-change` 提示 GPU 加速、长列表 `key` 优化、图片懒加载与 WebP 降级。
  5. 使用微信小程序性能面板与 `wx.getSystemInfoSync` 监控 FPS、内存泄漏与渲染耗时。
- **Prompt 模板**：
```md
编写高性能微交互与虚拟渲染组件，要求：
1. 骨架屏组件：支持静态/动态占位，数据加载完成后无缝过渡
2. 流式动画：模拟 AI 逐字输出，使用 requestAnimationFrame 节流，避免 setData 频繁调用
3. 虚拟列表：实现可视区计算、上下缓冲区、动态 item 高度，支持 1w+ 数据流畅滑动
4. 渲染优化：will-change 提示、图片懒加载、WebP 兼容、减少节点层级
5. 性能监控：内置 FPS 统计、内存水位预警、setData 耗时打点
6. 提供降级方案：低端机自动关闭动画/切换为简单分页
```
- **验收**：
  - ✅ 骨架屏占位准确，数据加载无缝衔接
  - ✅ 流式动画 60fps 稳定，无卡顿/内存泄漏
  - ✅ 虚拟列表渲染 1w+ 条目内存平稳，滑动无白屏
  - ✅ 首屏渲染时间 <1.5s，FPS >55

---

## Day 6：AI 辅助 Figma -> Tailwind 组件生成
- **目标**：掌握 AI 辅助前端工作流，实现设计稿到高保真代码的自动化转换。
- **实操**：
  1. 导出 Figma 设计稿（截图/JSON/SVG），构建结构化 Prompt（布局、组件名、状态、间距）。
  2. 使用 AI 生成 Tailwind CSS + 组件代码，校验类名规范与响应式断点。
  3. 清洗 AI 代码：适配小程序语法（`view`/`text` 替换 `div`/`span`，移除 `hover:`/`@media` 等不支持属性）。
  4. 建立 Design-to-Code 校验流水线：像素级 Diff 对比、可访问性检查、交互状态验证。
  5. 沉淀 Prompt 模板库，提升生成准确率与团队复用效率。
- **Prompt 模板**：
```md
构建 AI 辅助 Figma 到小程序代码转换流水线，要求：
1. 输入 Figma 截图/JSON，AI 生成 Tailwind + 组件结构代码
2. 自动语法转换：div->view, span->text, 移除不支持伪类/媒体查询
3. 视觉校验：像素级 Diff 对比，误差 >3px 标红提示，支持自动对齐修正
4. 可访问性检查：对比度 >4.5:1, 触摸区 >44x44px, 语义化标签
5. 沉淀 Prompt 模板：[组件类型][布局模式][交互状态] 组合生成器
6. 输出标准化代码片段，可直接注入项目 src/components
```
- **验收**：
  - ✅ AI 生成代码可用率 >80%，二次修改量 <20%
  - ✅ 小程序语法适配 100%，无编译报错
  - ✅ 视觉还原度 >90%，通过像素级 Diff 验证
  - ✅ 沉淀标准化 AI-to-Code Prompt 模板库

---

## Day 7：真机调试 + 体验版发布
- **目标**：完成全链路真机验证与发布流程，保障生产环境稳定性与可回滚。
- **实操**：
  1. 真机调试：多机型（iOS/Android 高低端）、多网络（4G/WiFi/弱网）交叉测试。
  2. 性能压测：内存监控（<200MB）、启动耗时、包体积优化（图片压缩、Tree Shaking、分包策略）。
  3. 异常监控：接入 Sentry/微信小程序错误日志，实现崩溃捕获、堆栈还原、用户行为回放。
  4. 配置体验版发布流程：CI/CD 自动构建、上传、体验版二维码生成、版本回滚预案。
  5. 输出发布 Checklist、线上监控看板与性能基线报告。
- **Prompt 模板**：
```md
编写小程序真机调试与 CI/CD 发布流水线，要求：
1. 多端真机测试矩阵：iOS/Android 高/低端机，4G/弱网模拟，覆盖核心路径
2. 性能压测：内存 <200MB，冷启动 <2s，主包 <2MB，分包按需加载
3. 异常监控：集成 Sentry/微信开放平台错误日志，崩溃堆栈还原，用户行为追踪
4. CI/CD 发布：GitHub Actions/GitLab CI 自动 build、upload、生成体验版二维码
5. 回滚机制：版本快照保存，一键降级至上一稳定版，灰度发布策略
6. 输出发布 Checklist：代码审核、性能基线、合规检查、监控接入确认
```
- **验收**：
  - ✅ 多端真机运行流畅，内存稳定 <200MB
  - ✅ 体验版一键发布，构建零报错，二维码可扫码
  - ✅ 异常监控接入，崩溃捕获率 100%，堆栈可定位
  - ✅ 发布文档与回滚预案完整，支持灰度/一键降级

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 工程一键初始化，TS/ESLint 零报错；支持 weapp/h5/alipay 多端编译；主包 <2MB |
| D2 | 状态跨页保持；持久化 TTL/LRU 正常；存储超限自动降级；弱网可读取快照 |
| D3 | 授权/登录无白屏；Token 无感刷新成功率 >99%；分享/订阅消息状态可审计 |
| D4 | 核心组件 Props 完整；暗色切换零闪烁；Design Tokens 覆盖 100%；类型提示完善 |
| D5 | 骨架屏无缝衔接；流式动画 60fps；虚拟列表 1w+ 数据流畅；FPS >55 |
| D6 | AI 代码可用率 >80%；小程序语法 100% 适配；视觉还原度 >90%；Prompt 模板库沉淀 |
| D7 | 真机内存 <200MB；体验版一键发布；崩溃监控 100% 覆盖；回滚预案可用 |

---

## 最终验收标准
- ✅ 真机运行流畅，内存峰值稳定 <200MB，无 OOM 或内存泄漏
- ✅ 授权/Token 刷新无断点，401 静默重试成功率 >99%
- ✅ UI 还原度 >90%，暗色/动态主题切换平滑，Design Tokens 统一管理
- ✅ 跨端框架编译零报错，主包/分包策略符合小程序规范
- ✅ AI 辅助 Figma->Code 流水线可用，生成代码二次修改量 <20%
- ✅ 体验版一键发布，异常监控接入，回滚预案完整可执行

---

## 高频 Prompt 模板
1. **跨端工程初始化与构建配置 Prompt**
   - Taro/UniApp 初始化与 TS/ESLint 严格模式
   - 多端环境变量与 postcss-pxtransform 配置
   - 路由拦截、全局 Error Boundary 与分包脚本
2. **状态管理与持久化缓存体系 Prompt**
   - Pinia/Zustand 模块化拆分与持久化插件
   - TTL/LRU 策略与微信 Storage 10MB 限制处理
   - 弱网兜底与缓存一致性校验
3. **微信核心能力与 Token 无感刷新 Prompt**
   - login/code2Session 流程与 401 静默重试
   - 动态分享卡片与订阅消息授权/发送管理
   - 平台适配层与合规降级策略
4. **设计系统与暗色主题组件库 Prompt**
   - Design Tokens 定义与 CSS 变量热更新
   - 核心业务组件开发与 Props/Slots 透传
   - 小程序 CSS 变量兼容与 Storybook 预览
5. **高性能微交互与虚拟渲染 Prompt**
   - 骨架屏占位与流式动画 RAF 节流
   - 虚拟列表可视区计算与动态高度
   - FPS/内存监控与低端机降级方案
6. **AI 辅助 Figma 到小程序代码转换 Prompt**
   - Figma 输入解析与 Tailwind 代码生成
   - div/span 替换与不支持属性清洗
   - 像素级 Diff 校验与 Prompt 模板沉淀
7. **真机调试与 CI/CD 发布流水线 Prompt**
   - 多端真机测试矩阵与性能压测
   - Sentry/微信错误日志接入与堆栈还原
   - 自动构建、上传、体验版二维码与回滚机制

---

## 动态调整建议
- **无跨端经验**：
  - 优先使用 `UniApp` 生态成熟度高，插件市场丰富；Taro 适合 React/Vue 深度定制
  - Day 1 聚焦微信单端，跑通后再扩展 H5/支付宝
- **UI/设计资源弱**：
  - Day 4/6 使用开源设计系统（如 `NutUI` / `Taro UI`）二次封装，快速对齐业务
  - AI 生成代码优先走“布局还原”路线，交互逻辑手动补充
- **性能瓶颈明显（卡顿/内存高）**：
  - Day 5 优先接入虚拟列表与 `setData` 节流，关闭非核心动画
  - 使用 `wx.getSystemInfoSync` 限制低端机资源消耗，开启 `enablePullDownRefresh` 按需加载
- **CI/CD 基础设施缺失**：
  - Day 7 先使用本地 `miniprogram-ci` 命令行上传，跑通后再迁移至 GitHub Actions
  - 监控可先用微信小程序后台“性能监控”面板，后期再接入 Sentry
- **团队前端栈不统一**：
  - 状态管理按技术栈选择：Vue 选 `Pinia`，React 选 `Zustand`/`Redux`，Prompt 模板提供双版本
  - 组件库使用 `Vue SFC` 或 `React Hooks` 隔离，保持业务逻辑与 UI 解耦
- **审核严格/合规要求高**：
  - Day 3 严格遵守微信授权规范：不强制登录、按需申请权限、隐私协议前置
  - 分享/订阅消息模板需提前在微信公众平台备案，Prompt 预留模板 ID 映射表

---

## 第 7 天自测清单
- [ ] 跨端项目一键初始化，TS/ESLint 零报错，多端编译产物符合规范
- [ ] 状态持久化读写正常，TTL/LRU 策略生效，Storage 超限自动清理
- [ ] Token 无感刷新拦截 401 成功，分享/订阅消息状态可追踪
- [ ] 核心组件库 Props 完整，暗色切换平滑，Design Tokens 覆盖 100%
- [ ] 骨架屏无缝衔接，流式动画 60fps，虚拟列表 1w+ 数据滑动无白屏
- [ ] AI 生成代码可用率 >80%，小程序语法适配 100%，视觉还原度 >90%
- [ ] 多端真机运行流畅，内存 <200MB，体验版一键发布成功
- [ ] 异常监控接入，崩溃捕获率 100%，回滚预案可执行
- [ ] 仓库包含：工程配置、组件库、状态管理、发布脚本、AI Prompt 库、性能基线报告
- [ ] 能清晰口述跨端架构选型、状态持久化策略、性能优化路径与发布回滚流程
