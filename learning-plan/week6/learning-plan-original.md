# Week 6: 小程序端接入与 UI/UX 精细化

## 🎯 目标
完成微信小程序接入，实现跨端同步与高还原度 UI。覆盖 Taro/Uniapp 多端构建、状态管理持久化、微信原生 API 集成、主题系统定制、微交互打磨、AI 辅助设计稿转码到真机发布全流程，最终交付可一键发布的生产级小程序。

---

## Day 1：Taro/Uniapp 初始化 + 多端构建

- **目标**：搭建跨端小程序项目骨架，跑通微信/H5/支付宝多端构建链路，建立标准化工程规范。
- **实操**：
  1. 使用 Taro CLI 初始化项目（React/Vue3 + TypeScript），配置 `project.config.json`。
  2. 搭建标准目录结构：`src/pages`、`src/components`、`src/stores`、`src/utils`、`src/assets`。
  3. 接入 Tailwind CSS（`weapp-tailwindcss`），配置 `postcss-pxtransform` 实现 px → rpx 自动转换（设计稿基准 750px）。
  4. 创建基础页面路由：首页、聊天页、设置页、个人中心，配置底部 TabBar。
  5. 封装 HTTP 请求层：Taro.request 拦截器，统一处理 Token 注入、错误提示、超时重试。
  6. 配置多端构建脚本与多环境变量（`.env.development` / `.env.production`），验证 dev:weapp、dev:h5、build:weapp 产物。
  7. 配置 ESLint + Prettier + Husky，CI 预检脚本（lint / type-check / build-dry-run）。
- **Prompt 模板**：

```md
使用 Taro 3.x 初始化跨端小程序项目，要求：

1. 使用 React + TypeScript 模板，集成 weapp-tailwindcss 适配小程序
2. 配置 postcss-pxtransform：750px 设计稿基准，rpx 自动转换
3. 搭建标准目录结构：pages / components / stores / utils / assets
4. 路由配置：首页(/pages/index)、聊天(/pages/chat)、设置(/pages/settings)
5. 封装 HTTP 请求层 utils/request.ts：
   - Taro.request 二次封装，自动注入 Authorization header
   - 统一错误处理（网络异常/401/500），Toast 提示
   - 超时 15s，失败自动重试 1 次
6. package.json scripts：
   - dev:weapp / dev:h5 / build:weapp / build:h5
7. 多环境变量管理 .env.development / .env.production，config/index.ts 分离环境配置
8. ESLint + Prettier + Husky 配置，CI 预检：lint + type-check
9. 主包体积控制 < 2MB，支持分包懒加载
```

- **验收**：
  - Taro H5 与微信开发者工具均可正常启动，多端编译零报错
  - 四个页面路由切换正常，TabBar 渲染正确，无白屏
  - HTTP 请求层封装完成，Token 注入与错误处理验证通过
  - 双端 UI 一致性 > 90%，主包体积 < 2MB

## Day 2：Pinia/Zustand 持久化 + 本地缓存策略

- **目标**：实现跨页面状态管理与本地持久化，保障离线可用与数据同步，处理微信 Storage 10MB 配额限制。
- **实操**：
  1. 安装 Pinia（Vue）或 Zustand（React），创建模块化 Store：userStore、chatStore、settingsStore。
  2. 实现持久化中间件：state 变更自动写入 `Taro.setStorageSync`，启动时自动恢复，处理序列化/反序列化。
  3. 设计本地缓存分层策略：
     - L1（Store）：内存级，高频读写，不持久化
     - L2（Storage）：会话记录、用户偏好，Key-Value，TTL 可配
     - L3（Filesystem）：图片/文件缓存，Taro.getFileSystemManager
  4. 实现缓存过期机制：TTL 过期自动清理，LRU 淘汰策略（Storage 接近 10MB 上限时自动清理低频数据）。
  5. 封装缓存工具类：`cache.get(key)`、`cache.set(key, value, ttl)`、`cache.remove(key)`、`cache.clear()`、`cache.getQuotaUsage()`。
  6. 弱网/断网场景：读取本地快照兜底，网络恢复后静默同步。
  7. 处理多端存储差异：H5 用 localStorage，小程序用 Taro Storage API，统一接口。
- **Prompt 模板**：

```md
实现小程序状态管理与持久化缓存方案，要求：

1. Zustand/Pinia Store 模块化拆分：
   - userStore：登录态、用户信息、Token
   - chatStore：会话列表、消息记录、草稿
   - settingsStore：主题、字体、通知偏好

2. 持久化中间件：
   - state 变更时自动同步至 Taro.setStorageSync
   - 应用启动时从 Storage 恢复 state
   - 序列化/反序列化处理，避免循环引用

3. 缓存分层策略：
   - L1（Store）：高频读写，内存级
   - L2（Storage）：会话记录/用户偏好，TTL 可配
   - L3（Filesystem）：图片/文件缓存

4. 缓存工具类 utils/cache.ts：
   - get(key) / set(key, value, ttl) / remove(key) / clear()
   - getQuotaUsage() / clearExpired() / forceSync()
   - 内置 LRU 淘汰，最大缓存数量可配
   - TTL 过期自动清理，输出存储水位日志

5. 微信 Storage 10MB 限制处理：
   - 超限自动清理低频 key + 过期数据
   - 写入前预检查配额，超限记录告警日志

6. 弱网兜底：断网读取本地快照，网络恢复静默同步
7. 多端适配：H5 用 localStorage，小程序用 Taro Storage API，统一接口
```

- **验收**：
  - 页面切换状态不丢失，刷新后 Store 自动恢复
  - 缓存工具类功能完整，TTL 过期自动清理，LRU 淘汰正常
  - Storage 超限自动降级，无崩溃/报错
  - 弱网/断网场景可读取本地快照并静默恢复
  - H5 与小程序缓存行为一致

## Day 3：微信授权/分享/订阅消息 API 接入

- **目标**：集成微信原生能力，打通登录授权、社交分享与消息触达链路，符合微信审核规范。
- **实操**：
  1. 接入微信登录：`wx.login()` 获取 code → 后端 `code2Session` 换取 openid/session_key/unionid → 静默登录返回 JWT Token。
  2. 实现 Token 无感刷新机制：
     - 请求拦截器检测 401，自动调用 `/api/v1/auth/refresh` 静默续期
     - 刷新期间请求队列暂存，新 Token 获取后批量重放
     - 刷新失败清除登录态，跳转登录页
  3. 实现用户授权：`wx.getUserProfile()` 获取头像昵称，处理授权拒绝降级（引导文案，不阻塞核心功能）。
  4. 接入分享功能：`wx.showShareMenu()` + `onShareAppMessage` / `onShareTimeline`，自定义标题、封面图、带参路径（source 追踪）。
  5. 接入订阅消息：`wx.requestSubscribeMessage()` 申请模板权限，缓存用户订阅状态，处理拒收与频次限制。
  6. 封装微信 API 统一调用层：`utils/wxAuth.ts`、`utils/wxShare.ts`、`utils/wxSubscribe.ts`，内置错误处理与降级。
  7. 安全合规：不强制授权，敏感操作按需触发，隐私协议前置。
- **Prompt 模板**：

```md
实现微信小程序授权、分享与订阅消息功能，要求：

1. 静默登录流程：
   - 调用 wx.login() 获取临时 code
   - 发送至后端 /api/v1/auth/wechat-login，code2Session 换取 openid/unionid
   - 返回 JWT token，存入 Storage，后续请求 Header 携带
   - 用户无弹窗感知

2. Token 无感刷新管理器：
   - 请求拦截器检测 401，自动调用 /api/v1/auth/refresh
   - 刷新期间请求队列暂存，新 Token 获取后批量重放
   - 刷新失败清除登录态，跳转登录页
   - 目标：401 静默重试成功率 > 99%

3. 用户授权封装 utils/wxAuth.ts：
   - getUserProfile() 获取头像/昵称
   - 处理拒绝授权：展示引导文案，不阻塞核心功能
   - getSetting() 检查权限状态，引导重新授权

4. 分享功能封装 utils/wxShare.ts：
   - wx.showShareMenu({ menus: ['shareAppMessage', 'shareTimeline'] })
   - onShareAppMessage 自定义标题、路径（带 source 参数）、封面图
   - 分享回调埋点：记录分享目标与成功/取消

5. 订阅消息封装 utils/wxSubscribe.ts：
   - requestSubscribeMessage(tmplIds) 申请单次/长期订阅
   - 缓存用户订阅状态，避免重复弹窗
   - 发送成功/拒收日志上报，模板 ID 映射管理

6. 平台适配层：统一 wx.* 与 Web API 差异
7. 安全合规：不强制授权，按需申请权限，隐私协议前置
8. H5 环境降级：扫码/链接分享替代
```

- **验收**：
  - 静默登录完整闭环，Token 无感刷新，401 重试成功率 > 99%
  - 分享内容自定义后正确展示，带参路径可追踪
  - 订阅消息弹窗正常，用户勾选/拒收状态可审计
  - 授权拒绝降级方案不影响核心功能

## Day 4：组件库定制 + 暗色/动态主题

- **目标**：构建高复用业务组件库，实现 Design Token 驱动主题系统与暗色模式无缝切换。
- **实操**：
  1. 提取 UI 规范，定义 Design Token：颜色、字体、圆角、阴影、间距，导出 CSS 变量与 TS 常量。
  2. 开发核心业务组件：NavBar、Button、Input、Card、Dialog、Toast、Loading、Empty、Error，支持 Props 透传、Slot 扩展与类型提示。
  3. 实现暗色模式：CSS 变量切换方案，`data-theme` 属性驱动，监听 `prefers-color-scheme` 跟随系统主题。
  4. 封装 ThemeProvider 组件：全局注入主题上下文，支持手动切换（亮色/暗色/跟随系统），切换后持久化至 Storage。
  5. CSS 变量兼容性：旧版 Android 降级为 class 切换，移除小程序不支持属性（如 backdrop-filter）。
  6. 主题切换动画：0.3s 平滑过渡，避免闪烁。
  7. 导出 `.d.ts` 完整 Props 类型定义，IDE 智能提示。
- **Prompt 模板**：

```md
实现小程序组件库定制与主题系统，要求：

1. Design Token 定义 theme/tokens.ts：
   - 颜色：primary、secondary、success、warning、error、bg、text、border
   - 字体：size-xs/sm/base/lg/xl、weight-normal/medium/bold
   - 间距：spacing-2/4/6/8/12/16/24/32
   - 圆角：radius-sm/md/lg/full
   - 阴影：shadow-sm/md/lg
   - 导出 CSS 变量与 JS 常量双版本

2. CSS 变量方案 theme/variables.css：
   - 所有 Token 映射为 --color-primary、--font-size-base 等
   - 暗色模式通过 [data-theme="dark"] 覆写变量
   - transition: background-color 0.3s, color 0.3s 平滑过渡

3. ThemeProvider 组件 components/ThemeProvider：
   - 读取系统主题偏好 wx.getSystemInfoSync().theme
   - 支持手动切换（亮色/暗色/跟随系统）
   - 切换后写入 Storage 持久化，Context 注入

4. 核心业务组件：
   - NavBar：自定义标题、返回按钮、右侧操作区
   - Button：primary/secondary/outline/text 四种变体 + loading/disabled 状态
   - Card、Input、Dialog、Toast、Loading、Empty、Error
   - 所有组件 Props 完整透传，支持 Slot 扩展

5. 小程序兼容：
   - CSS 变量降级策略：旧版 Android 降级为 class 切换
   - 移除不支持属性（backdrop-filter、::before/::after 复杂用法）
   - 触摸区 > 44×44px 符合微信规范

6. 导出 .d.ts 完整 Props 类型定义
```

- **验收**：
  - 核心组件库封装完成，Props 类型完整
  - 暗色/亮色主题一键切换，全局组件同步更新，零闪烁
  - Design Token 覆盖 100% 业务样式，零硬编码
  - 组件文档清晰，可独立复用，类型提示完善

## Day 5：微交互（骨架屏/流式动画/虚拟列表）

- **目标**：打磨交互细节，通过骨架屏、流式动画、虚拟列表与 Lottie 提升加载体验与长列表性能。
- **实操**：
  1. 实现骨架屏（Skeleton Screen）：支持 text/avatar/image/card 四种形状占位，呼吸动画，加载完成自动渐隐过渡。
  2. 实现流式打字动画：逐字渲染 AI 回复，间隔 30-50ms，`requestAnimationFrame` 节流避免频繁 setData，支持 Markdown 实时解析。
  3. 实现虚拟列表（Virtual List）：仅渲染可视区 + 上下缓冲区 DOM，动态 item 高度，支撑 10000+ 消息流畅滚动。
  4. 优化滚动体验：新消息自动滚底，用户手动上滑时暂停并提示"新消息"气泡，点击恢复。
  5. Lottie 动画集成：点赞/发送/加載中 3 组动画，`lottie-miniprogram` 控制播放，预加载避免首次卡顿。
  6. 性能优化：批量合并 setData 调用，图片懒加载，`will-change` 提示 GPU 加速，wxs 响应事件减少通信。
  7. FPS 监控与低端机降级：内置 FPS 统计、内存水位预警，低端机自动关闭动画/切换简单分页。
- **Prompt 模板**：

```md
实现小程序微交互与性能优化，要求：

1. 骨架屏组件 components/Skeleton：
   - text/avatar/image/card 四种占位形状，自动匹配容器尺寸
   - 呼吸动画（opacity 0.4 ↔ 1.0），loading 结束自动 fadeOut
   - 与真实内容同容器，避免布局跳动

2. 流式打字动画 components/StreamingText：
   - 逐字渲染 AI 回复，间隔 30-50ms 可配
   - requestAnimationFrame 节流，避免频繁 setData
   - 光标闪烁效果（| 字符 opacity 动画）
   - Markdown 实时解析：代码块/加粗/链接
   - 用户手动上滑暂停自动滚动，支持暂停/继续

3. 虚拟列表 hooks/useVirtualList：
   - 仅渲染可视区 + overscanCount 缓冲区 DOM
   - 计算总高度、可视起止索引、偏移量
   - 动态 item 高度，支撑 10000+ 数据流畅滑动
   - 搭配 scroll-view bindscroll 事件实现

4. 滚动优化 hooks/useScrollToBottom：
   - 新消息自动滚底，用户上滑暂停
   - "新消息"气泡提示，点击恢复自动滚动

5. Lottie 动画集成：
   - 点赞、发送、加載中 3 组动画
   - 使用 lottie-miniprogram 控制播放
   - 预加载动画资源，避免首次播放卡顿

6. 性能优化：
   - 批量更新：合并多次 setData 调用
   - 图片懒加载 lazy-load，WebP 优先降级
   - will-change 提示 GPU 加速，减少节点层级
   - 长列表 wxs 响应事件，减少通信开销

7. FPS 监控：内置统计、内存水位预警、setData 耗时打点
8. 低端机降级：自动关闭动画/切换简单分页，限制资源消耗
```

- **验收**：
  - 骨架屏过渡自然，无布局跳动
  - 流式打字 60fps 稳定，无卡顿/内存泄漏，Markdown 渲染正确
  - 虚拟列表 10000+ 消息内存平稳，滑动无白屏，帧率 > 55fps
  - Lottie 动画播放流畅，预加载无延迟
  - 自动滚动逻辑正确，用户上滑不被中断

## Day 6：AI 辅助 Figma → Tailwind 组件生成

- **目标**：建立 AI 驱动的设计稿到代码流水线，实现高还原度组件自动生成与标准化校验。
- **实操**：
  1. 从 Figma 导出设计稿（截图/JSON/Dev Mode），整理为结构化 Prompt 输入（布局、组件名、状态、间距）。
  2. 让 AI 生成 Tailwind CSS + Taro 组件代码，指定响应式断点与交互状态（hover/active/disabled）。
  3. 代码清洗：自动语法转换（div → view、span → text），移除小程序不支持伪类/媒体查询/Hover。
  4. 视觉校验：像素级 Diff 对比，误差 > 3px 标红提示，量化还原度。
  5. 可访问性检查：对比度 > 4.5:1、触摸区 > 44×44px、语义化标签、aria-label。
  6. 建立组件生成规范：Props 接口定义、loading/empty/error 三态覆盖，使用 Design Token 变量。
  7. 沉淀 Prompt 模板库：卡片、列表、表单、导航栏、弹窗等高频组件模板。
- **Prompt 模板**：

```md
构建 AI 辅助 Figma 到小程序代码转换流水线，要求：

输入格式（二选一）：
- Figma 截图：附组件类型、尺寸、颜色、字体、间距、交互状态描述
- Figma Dev Mode JSON：auto layout、constraints、layer names

设计描述模板：
- 组件类型：{card/list/form/navbar/modal}
- 尺寸：{width} × {height}
- 颜色：背景{color}、文字{color}、边框{color}
- 字体：{fontFamily} {fontSize} {fontWeight}
- 间距：padding {top/right/bottom/left}，gap {value}
- 圆角：{value}，阴影：{value}
- 交互状态：hover/active/disabled 效果描述

生成要求：
1. Taro 组件 + Tailwind CSS（weapp-tailwindcss 适配）
2. TypeScript 完整 Props 接口定义
3. 自动语法转换：div→view、span→text，移除不支持属性
4. loading / empty / error 三种状态覆盖
5. 使用 Design Token 变量（var(--color-primary)），禁止硬编码
6. 响应式适配：H5 与小程序双端
7. 附组件使用示例代码

校验标准：
- 像素级 Diff：视觉还原度 > 90%，误差 > 3px 标红
- 可访问性：对比度 > 4.5:1、触摸区 > 44×44px、语义化标签
```

- **验收**：
  - AI 生成组件可编译运行，代码可用率 > 80%，二次修改量 < 20%
  - 视觉还原度 > 90%，通过像素级 Diff 验证
  - 小程序语法适配 100%，无编译报错
  - 沉淀标准化 Prompt 模板 >= 5 个高频组件类型

## Day 7：真机调试 + 体验版发布 + CI/CD

- **目标**：完成全链路真机验证与自动化发布流程，保障生产环境稳定性与可回滚。
- **实操**：
  1. 真机调试矩阵：iOS（iPhone 12/13/14/15）+ Android（华为/小米中高端），4G/WiFi/弱网交叉测试。
  2. 核心路径验证：登录流程 → 聊天链路 → 分享 → 主题切换 → 网络切换。
  3. 性能压测：冷启动 < 2s、页面切换 < 0.5s、内存 < 200MB、帧率 > 50fps、主包 < 2MB。
  4. 异常监控集成：接入 Sentry/微信开放平台错误日志，全局 `App.onError` + `Taro.onUnhandledRejection` 捕获，崩溃堆栈还原，脱敏处理。
  5. 埋点验证：自动化发送测试事件，覆盖 page_view / click / conversion，验证平台接收正常。
  6. 体验版发布流程：
     - CI/CD 自动构建（GitHub Actions/GitLab CI）
     - `miniprogram-ci` 自动上传 + 生成体验版二维码
     - 邀请测试成员 → 收集反馈 → Bug 修复
  7. 审核材料准备：隐私协议、用户协议、功能截图、测试账号。
  8. 回滚预案：版本快照保存，一键降级至上一稳定版，灰度发布策略。
  9. 发布 Checklist：环境切换确认、API 域名白名单、AppID、版本号管理。
- **Prompt 模板**：

```md
编写小程序真机调试与 CI/CD 发布流水线，要求：

1. 真机测试矩阵（checklist/device-test.md）：
   - iOS 14+（iPhone 12/13/14/15 系列）
   - Android 10+（华为 Mate/P 系列、小米数字系列）
   - 4G/WiFi/弱网模拟，覆盖核心路径
   - 性能基线：冷启动 < 2s、页面切换 < 0.5s、内存 < 200MB

2. 异常监控集成 utils/errorMonitor.ts：
   - 全局错误捕获：App.onError + Taro.onUnhandledRejection
   - 关键路径 try-catch：支付、登录、核心 API 调用
   - Sentry.init() 上报：设备信息、页面路径、堆栈还原
   - 脱敏处理：自动过滤手机号、身份证等敏感信息

3. 埋点验证 utils/analytics-verify.ts：
   - 自动化发送测试事件
   - 覆盖 page_view / click / conversion 三类核心事件
   - 验证平台数据接收正常

4. CI/CD 发布流水线（.github/workflows/release.yml）：
   - Stage 1：lint + type-check + build
   - Stage 2：miniprogram-ci 自动上传
   - Stage 3：生成体验版二维码，通知测试群

5. 发布与回滚方案 docs/release.md：
   - 环境切换 config/env.ts：dev/staging/prod 三套，API 域名白名单自动切换
   - 发布前强制检查：当前环境、域名白名单、AppID
   - 回滚机制：版本快照保存，一键降级至上一稳定版
   - 灰度发布：按 percentage 逐步放量

6. 审核材料：隐私协议、用户协议、功能截图、测试账号
```

- **验收**：
  - iOS + Android 主流机型测试通过，核心路径无 Crash
  - 启动 < 2s，内存 < 200MB，帧率 > 50fps，主包 < 2MB
  - 异常监控上报正常，崩溃捕获率 100%，堆栈可定位
  - 埋点数据可查，三类核心事件上报正常
  - 体验版一键发布成功，CI/CD 流水线零报错
  - 发布 Checklist 完整，回滚/灰度预案可执行

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 工程一键初始化，TS/ESLint 零报错；支持 weapp/h5 多端编译；4 页面路由正常；HTTP 封装完成；双端一致性 > 90%；主包 < 2MB |
| D2 | 状态跨页保持；持久化 TTL/LRU 正常；Storage 超限自动降级；弱网可读取快照；H5 与小程序缓存行为一致 |
| D3 | 授权/登录流程完整，无白屏；Token 无感刷新，401 重试成功率 > 99%；分享/订阅消息状态可审计；授权拒绝降级不阻塞 |
| D4 | 核心组件 Props 完整；暗色切换零闪烁；Design Token 覆盖 100%；类型提示完善；组件可独立复用 |
| D5 | 骨架屏过渡自然无跳动；流式打字 60fps；虚拟列表 10000+ 数据顺畅，帧率 > 55fps；Lottie 动画流畅；低端机降级可用 |
| D6 | AI 代码可用率 > 80%；小程序语法 100% 适配；还原度 > 90%（像素级 Diff）；Prompt 模板 >= 5 个 |
| D7 | 真机双端测试无 Crash；内存 < 200MB、启动 < 2s；异常监控崩溃捕获 100%；体验版一键发布；回滚/灰度预案可执行 |

## 最终验收标准

- 微信小程序在 iOS/Android 主流机型上运行流畅，内存 < 200MB，启动 < 2s，帧率 > 50fps
- 用户授权/Token 刷新无断点，401 静默重试成功率 > 99%
- UI 还原度 > 90%，暗色/动态主题切换平滑，Design Token 覆盖 100%
- 骨架屏过渡自然、流式打字 60fps、虚拟列表高性能、Lottie 动画丝滑
- AI 辅助 Figma → Code 流水线可用，代码可用率 > 80%，Prompt 模板沉淀 >= 5 个
- CI/CD 自动构建与上传，体验版一键发布成功，回滚/灰度预案完整可执行
- 异常监控崩溃捕获率 100%，埋点关键事件数据可查

## 高频 Prompt 模板

1. **Taro 跨端项目初始化 Prompt**
   - React/Vue3 + TypeScript + weapp-tailwindcss
   - postcss-pxtransform + 分包策略 + 多环境变量
   - HTTP 请求层封装 + CI 预检脚本
   - 主包体积控制 < 2MB

2. **小程序持久化状态管理 Prompt**
   - Pinia/Zustand 模块化拆分 + 持久化中间件
   - 三层缓存策略（Store/Storage/Filesystem）
   - TTL + LRU 淘汰 + 10MB 配额监控
   - 弱网兜底 + 静默同步

3. **微信授权/分享/订阅消息集成 Prompt**
   - 静默登录 + code2Session + Token 无感刷新（401 重试 > 99%）
   - 用户授权降级处理 + 动态分享卡片 + 订阅消息管理
   - 平台适配层 + 安全合规降级

4. **暗色/动态主题系统 Prompt**
   - Design Token 定义（颜色/字体/间距/圆角/阴影）
   - CSS 变量热更新 + ThemeProvider 跟随系统
   - 小程序兼容（class 降级、移除不支持属性）
   - .d.ts 完整 Props 类型导出

5. **微交互（骨架屏/流式动画/虚拟列表）Prompt**
   - 骨架屏多形状占位 + 渐隐过渡
   - 流式打字 + Markdown 实时解析（RAF 节流）
   - 虚拟列表（可视区 + 缓冲区 + 动态高度）
   - Lottie 动画 + FPS 监控 + 低端机降级

6. **Figma → Tailwind 组件生成 Prompt**
   - 结构化设计描述输入（截图/JSON/SVG）
   - Taro 语法自动清洗 + Design Token 变量
   - 像素级 Diff 校验（误差 > 3px 标红）
   - 可访问性检查（对比度 > 4.5:1、触摸区 > 44×44px）

7. **真机调试与 CI/CD 发布流水线 Prompt**
   - 多端真机矩阵 + 弱网模拟 + 性能基线
   - Sentry 异常监控 + 埋点验证
   - CI/CD 自动构建上传 + 体验版二维码
   - 版本快照回滚 + 灰度发布 + 审核材料

## 动态调整建议

- **无跨端经验**：Day 1 先聚焦微信单端跑通，再扩展 H5；UniApp 生态更成熟可选。
- **UI/设计资源弱**：Day 4/6 使用开源设计系统（NutUI/Taro UI）二次封装，AI 优先还原布局，交互逻辑手动补。
- **有 Figma 设计稿**：Day 6 可提前至 Day 1 并行，用 AI 辅助生成，缩短设计-开发周期。
- **有 H5 现成代码**：Day 1-2 聚焦 Taro 适配与小程序 API 替换，组件逻辑直接复用。
- **性能瓶颈明显**：Day 5 优先接入虚拟列表 + setData 节流，低端机关闭非核心动画，使用 wxs 减少通信开销。
- **CI/CD 基础设施缺失**：Day 7 先本地 `miniprogram-ci` 上传，跑通后再迁移至 GitHub Actions；监控先用微信后台面板，后期接入 Sentry。
- **审核严格 / 合规要求高**：Day 3 严格遵守微信授权规范（不强制登录、按需申请权限、隐私协议前置），分享/订阅模板提前在微信公众平台备案。
- **团队前端栈不统一**：Vue 选 Pinia + NutUI，React 选 Zustand + Taro UI，Prompt 模板提供双版本。

## 第 7 天自测清单

- [ ] 跨端项目一键初始化，TS/ESLint 零报错，多端编译产物符合规范，主包 < 2MB
- [ ] 状态持久化读写正常，TTL/LRU 策略生效，Storage 超限自动清理，弱网可读快照
- [ ] Token 无感刷新拦截 401 成功（重试率 > 99%），分享/订阅消息状态可追踪
- [ ] 核心组件 Props 类型完整，暗色切换平滑零闪烁，Design Token 覆盖 100%
- [ ] 骨架屏无缝衔接，流式动画 60fps，虚拟列表 10000+ 数据滑动无白屏，Lottie 流畅
- [ ] AI 生成代码可用率 > 80%，小程序语法 100% 适配，像素级 Diff 还原度 > 90%
- [ ] 多端真机运行流畅，内存 < 200MB，启动 < 2s，帧率 > 50fps
- [ ] CI/CD 自动化构建上传，体验版一键发布成功，回滚/灰度预案可执行
- [ ] 异常监控崩溃捕获 100%，埋点关键事件数据正常
- [ ] 仓库包含：工程配置、组件库、状态管理、发布脚本、AI Prompt 库、性能基线报告、发布 Checklist
- [ ] 能清晰口述跨端架构选型、状态持久化策略、微信 API 集成、性能优化路径与 CI/CD 发布回滚流程
