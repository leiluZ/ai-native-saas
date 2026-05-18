# Week 6: 小程序端接入与 UI/UX 精细化

## 🎯 目标
完成微信小程序接入，实现跨端同步与高还原度 UI。覆盖 Taro/Uniapp 多端构建、状态管理持久化、微信原生 API 集成、主题系统定制、微交互打磨、AI 辅助组件生成到真机发布全流程。

---

## Day 1：Taro/Uniapp 初始化 + 多端构建

- **目标**：搭建跨端小程序项目骨架，跑通 H5 与微信小程序双端构建链路。
- **实操**：
  1. 使用 Taro CLI 初始化项目（React/Vue3 择一），配置 `project.config.json`。
  2. 接入 Tailwind CSS（`@tarojs/plugin-html` 或 `weapp-tailwindcss`），配置小程序尺寸单位适配。
  3. 创建基础页面路由：首页、聊天页、设置页、个人中心。
  4. 封装 HTTP 请求层：Taro.request 拦截器，统一处理 Token 注入、错误提示、超时重试。
  5. 配置多端构建脚本：H5 Dev、Weapp Dev、Weapp Build，验证两端预览一致性。
  6. 配置 ESLint + Prettier，确保代码规范统一。
- **Prompt 模板**：

```md
使用 Taro 3.x 初始化小程序项目，要求：

1. 使用 React + TypeScript 模板，集成 weapp-tailwindcss 适配小程序
2. 创建路由配置：首页(/pages/index)、聊天(/pages/chat)、设置(/pages/settings)
3. 封装 HTTP 请求层 utils/request.ts：
   - Taro.request 二次封装
   - 自动注入 Authorization header
   - 统一错误处理（网络异常/401/500），Toast 提示
   - 超时 15s，失败自动重试 1 次
4. 配置 package.json scripts：
   - dev:h5 (Taro H5 开发)
   - dev:weapp (微信小程序开发)
   - build:weapp (微信小程序生产构建)
5. 基础配置文件 config/index.ts：分离 dev/prod 环境变量
6. ESLint + Prettier 配置，确保团队代码风格一致
```

- **验收**：
  - Taro H5 与微信开发者工具均可正常启动
  - 四个页面路由切换正常，无白屏
  - HTTP 请求层封装完成，Token 注入与错误处理验证通过
  - 双端 UI 一致性 > 90%

## Day 2：Pinia/Zustand 持久化 + 本地缓存策略

- **目标**：实现跨页面状态管理与本地持久化，保障离线可用与数据同步。
- **实操**：
  1. 安装 Pinia（Vue）或 Zustand（React），创建全局 Store：user、chat、settings。
  2. 实现持久化插件：state 变更自动写入 `Taro.setStorageSync`，启动时自动恢复。
  3. 设计本地缓存分层策略：热数据存 Store（高频读写）、温数据存 Storage（会话记录）、冷数据存 Filesystem（图片/文件缓存）。
  4. 实现缓存过期机制：设置 TTL，过期自动清理，LRU 淘汰策略。
  5. 封装缓存工具库：`cache.get(key)`、`cache.set(key, value, ttl)`、`cache.clear()`。
  6. 处理多端存储差异：H5 使用 localStorage，小程序使用 Storage API，统一接口。
- **Prompt 模板**：

```md
实现小程序状态管理与持久化缓存方案，要求：

1. Zustand/Pinia Store 设计：
   - userStore：登录态、用户信息、Token
   - chatStore：会话列表、消息记录、草稿
   - settingsStore：主题、字体、通知偏好

2. 持久化中间件：
   - state 变更时自动同步至 Taro.setStorageSync
   - 应用启动时从 Storage 恢复 state
   - 序列化/反序列化处理，避免循环引用

3. 缓存分层策略：
   - L1（Store）：高频读写，内存级，不持久化
   - L2（Storage）：会话记录、用户偏好，Key-Value，TTL 可配
   - L3（Filesystem）：图片/文件缓存，Taro.getFileSystemManager

4. 缓存工具类 utils/cache.ts：
   - get(key)、set(key, value, ttl)、remove(key)、clear()
   - 内置 LRU 淘汰，最大缓存数量可配
   - 自动序列化/反序列化 JSON
   - 过期数据自动清理

5. 多端适配：H5 用 localStorage，小程序用 Taro Storage API，统一接口
```

- **验收**：
  - 页面切换后状态不丢失，刷新后 Store 自动恢复
  - 缓存工具类功能完整，TTL 过期自动清理
  - 存储配额管理正常，无超限崩溃
  - H5 / 小程序缓存行为一致

## Day 3：微信授权/分享/订阅消息 API 接入

- **目标**：集成微信原生能力，打通登录授权、社交分享与消息触达链路。
- **实操**：
  1. 接入微信登录：`wx.login()` 获取 code -> 后端换取 openid/session_key -> 静默登录。
  2. 实现用户授权：`wx.getUserProfile()` 获取头像昵称，处理授权拒绝降级。
  3. 接入分享功能：`wx.showShareMenu()` + `onShareAppMessage` 自定义分享内容。
  4. 接入订阅消息：`wx.requestSubscribeMessage()` 申请模板消息权限，处理用户勾选状态。
  5. 封装微信 API 统一调用层：`wxApi.login()`、`wxApi.share()`、`wxApi.subscribe()`，内置错误处理与降级。
  6. 实现 Token 刷新机制：access_token 过期自动用 refresh_token 续期，无感刷新。
- **Prompt 模板**：

```md
实现微信小程序授权、分享与订阅消息功能，要求：

1. 静默登录流程：
   - 调用 wx.login() 获取临时 code
   - 发送至后端 /api/v1/auth/wechat-login 换取 openid 和 session_key
   - 返回 JWT token，存入 Storage，后续请求 Header 携带
   - 用户无需感知，无弹窗

2. 用户授权封装 utils/wxAuth.ts：
   - getUserProfile()：获取头像/昵称
   - 处理拒绝授权场景：展示引导文案，不阻塞核心功能
   - 检查权限状态 getSetting()，引导重新授权

3. 分享功能封装 utils/wxShare.ts：
   - 全局开启分享：wx.showShareMenu({ menus: ['shareAppMessage', 'shareTimeline'] })
   - onShareAppMessage 自定义标题、路径、图片
   - 分享回调埋点：记录分享目标与成功/取消

4. 订阅消息封装 utils/wxSubscribe.ts：
   - requestSubscribeMessage(tmplIds)：申请单次/长期订阅
   - 缓存用户订阅状态，避免重复弹窗
   - 模板 ID 集中管理于 config/subscribeTemplates.ts

5. Token 刷新管理器：
   - 请求拦截器检测 401，自动调用 /api/v1/auth/refresh
   - 刷新期间请求队列暂存，新 Token 获取后批量重放
   - 刷新失败清除登录态，跳转登录页

6. 降级策略：非微信环境（H5）提供 Web 端替代交互（扫码/链接分享）
```

- **验收**：
  - 静默登录完整闭环，Token 无感刷新
  - 分享内容自定义后正确展示
  - 订阅消息弹窗正常，用户勾选状态正确记录
  - 授权拒绝降级方案不影响核心功能

## Day 4：组件库定制 + 暗色/动态主题

- **目标**：构建定制化组件库，实现暗色/动态主题一键切换与 Token 级样式管理。
- **实操**：
  1. 选型组件库（Taro UI / NutUI / 自研），按设计规范覆盖基础组件。
  2. 定义 Design Token：颜色、字体、圆角、阴影、间距，导出 CSS 变量或 JS 常量。
  3. 实现暗色模式：CSS 变量切换方案，`data-theme` 属性驱动，支持跟随系统主题。
  4. 封装 ThemeProvider 组件：全局注入主题上下文，支持运行时切换与持久化。
  5. 组件定制示例：自定义 NavBar、加载动画、空状态、错误提示。
  6. 编写组件文档与 Storybook（可选），确保组件可复用。
- **Prompt 模板**：

```md
实现小程序组件库定制与主题系统，要求：

1. Design Token 定义 theme/tokens.ts：
   - 颜色：primary、secondary、success、warning、error、bg、text
   - 字体：size-xs/sm/base/lg/xl、weight-normal/medium/bold
   - 间距：spacing-2/4/6/8/12/16/24
   - 圆角：radius-sm/md/lg/full
   - 阴影：shadow-sm/md/lg

2. CSS 变量方案 theme/variables.css：
   - 所有 Token 映射为 --color-primary、--font-size-base 等
   - 暗色模式通过 [data-theme="dark"] 覆写变量
   - 动画过渡：transition: background-color 0.3s, color 0.3s

3. ThemeProvider 组件 components/ThemeProvider：
   - 读取系统主题偏好 wx.getSystemInfoSync().theme
   - 支持手动切换（亮色/暗色/跟随系统）
   - 切换后写入 Storage 持久化
   - Context 注入当前主题，全局组件可消费

4. 定制基础组件：
   - NavBar：自定义标题、返回按钮、右侧操作区
   - Loading：三种样式（spinner/skeleton/dot-wave）
   - Empty：插画 + 提示文案 + 操作按钮
   - Error：错误码 + 文案 + 重试按钮

5. 主题切换动画：0.3s 平滑过渡，避免闪烁
6. 组件文档：每个组件附带 Props 说明、使用示例
```

- **验收**：
  - 暗色/亮色主题一键切换，全局组件同步更新
  - 跟随系统主题功能正常
  - Design Token 完整覆盖基础组件样式
  - 定制组件文档清晰，可复用

## Day 5：微交互（骨架屏/流式动画/虚拟列表）

- **目标**：打磨交互细节，通过骨架屏、流式动画与虚拟列表提升加载体验与长列表性能。
- **实操**：
  1. 实现骨架屏（Skeleton Screen）：自动匹配内容区形状，呼吸动画，加载完成后渐隐过渡。
  2. 实现流式打字动画：逐字/逐行渲染 AI 回复，支持光标闪烁与 Markdown 实时解析。
  3. 实现虚拟列表（Virtual List）：仅渲染可视区域 DOM，支撑 1000+ 条消息流畅滚动。
  4. 优化滚动体验：`scroll-view` 锚点定位、上拉加载更多、下拉刷新。
  5. 实现 Lottie 动画集成：点赞/发送等操作反馈动画。
  6. 性能优化：避免频繁 setData/forceUpdate，使用 `nextTick` 或批量更新。
- **Prompt 模板**：

```md
实现小程序微交互与性能优化，要求：

1. 骨架屏组件 components/Skeleton：
   - 支持 text/avatar/image/card 四种占位形状
   - 自动匹配容器尺寸，呼吸动画（opacity 0.4 <-> 1.0）
   - loading 结束自动 fadeOut，平滑过渡至真实内容
   - 与真实内容同容器，避免布局跳动

2. 流式打字动画 components/StreamingText：
   - 逐字渲染 AI 回复，间隔 30-50ms 可配
   - 光标闪烁效果（| 字符 opacity 动画）
   - Markdown 实时解析：代码块/加粗/链接
   - 自动滚动至最新内容，用户手动上滑时暂停
   - 支持暂停/继续，避免阻塞 UI 线程

3. 虚拟列表 hooks/useVirtualList：
   - 仅渲染可视区 + 上下缓冲（overscanCount）内的项
   - 计算总高度、可视起止索引、偏移量
   - 支撑 1000+ 条消息流畅滚动，帧率 > 50fps
   - 搭配 scroll-view bindscroll 事件实现

4. 滚动优化 hooks/useScrollToBottom：
   - 新消息自动滚动至底部
   - 用户手动上滑时暂停自动滚动，提示"新消息"气泡
   - 点击气泡/发送新消息后恢复自动滚动

5. Lottie 动画集成：
   - 点赞、发送、加载中 3 组动画
   - 使用 lottie-miniprogram 控制播放
   - 预加载动画资源，避免首次播放卡顿

6. 性能优化：
   - 批量更新：合并多次 setData 调用
   - 图片懒加载：lazy-load 属性
   - 长列表使用 wxs 响应事件，减少通信开销
```

- **验收**：
  - 骨架屏过渡自然，无布局跳动
  - 流式打字流畅不卡顿，Markdown 渲染正确
  - 虚拟列表 1000 条消息滚动帧率 > 50fps
  - Lottie 动画播放流畅，加载无延迟
  - 自动滚动逻辑正确，用户上滑不被中断

## Day 6：AI 辅助 Figma → Tailwind 组件生成

- **目标**：建立 AI 驱动的设计稿到代码流水线，实现高还原度组件自动生成。
- **实操**：
  1. 从 Figma 导出设计稿截图或 Dev Mode 代码片段，整理为结构化 Prompt 输入。
  2. 让 AI 生成 Tailwind/Taro 组件代码，指定断点适配、交互状态（hover/active/disabled）。
  3. 人工审核 AI 输出：对比设计稿还原度，修正间距/颜色/字体偏差。
  4. 建立组件生成规范：Props 接口定义、响应式断点策略、无障碍标准。
  5. 沉淀 Prompt 模板库：卡片、列表、表单、导航栏等高频组件的生成模板。
  6. 对比原始设计稿与生成代码截图，量化还原度 > 90%。
- **Prompt 模板**：

```md
根据 Figma 设计稿生成 Taro 小程序组件，要求：

设计描述：
- 组件类型：{card/list/form/navbar/modal}
- 尺寸：{width} × {height}
- 颜色：背景{color}、文字{color}、边框{color}
- 字体：{fontFamily} {fontSize} {fontWeight}
- 间距：padding {top/right/bottom/left}，gap {value}
- 圆角：{value}，阴影：{value}
- 交互状态：
  - hover：{效果描述}
  - active：{效果描述}
  - disabled：{效果描述}

生成要求：
1. 使用 Taro 组件 + Tailwind CSS（weapp-tailwindcss 适配）
2. TypeScript 完整类型 Props 接口定义
3. 响应式适配：H5 与小程序双端均需考虑
4. 包含 loading、empty、error 三种状态
5. 无障碍属性：aria-label、role
6. 使用 Design Token 变量（如 var(--color-primary)）而非硬编码
7. 附组件使用示例代码
```

- **验收**：
  - AI 生成组件可编译运行
  - 设计稿还原度 > 90%
  - 组件 Props 接口完整，三种状态覆盖
  - Prompt 模板沉淀 >= 5 个高频组件类型

## Day 7：真机调试 + 体验版发布

- **目标**：完成真机兼容性测试与体验版发布流程，确保生产级交付质量。
- **实操**：
  1. 真机调试：iOS + Android 双端兼容性测试，覆盖主流机型（iPhone 14/15、华为/小米中高端）。
  2. 性能检测：使用微信开发者工具 Performance 面板 / `wx.getPerformance()` 监测启动耗时、内存占用、帧率。
  3. 异常监控集成：接入 Sentry 或自研错误收集，全局 `onError` 捕获 + 关键路径 try-catch。
  4. 体验版发布：上传代码 -> 设置体验版 -> 邀请测试成员 -> 收集反馈。
  5. 审核材料准备：隐私协议、用户协议、功能截图、测试账号。
  6. 编写发布 Checklist：环境切换、API 域名白名单、版本号管理。
  7. 埋点验证：检查关键页面的 PV、点击、留存等数据上报。
- **Prompt 模板**：

```md
编写小程序真机调试与发布流程脚本/文档，要求：

1. 真机测试 Checklist（checklist/device-test.md）：
   - iOS 14+ 覆盖（iPhone 12/13/14/15 系列）
   - Android 10+ 覆盖（华为 Mate/P 系列、小米数字系列）
   - 测试项：登录流程、聊天核心链路、分享、支付、主题切换、网络切换
   - 性能基线：启动 < 2s、页面切换 < 0.5s、内存 < 200MB

2. 异常监控集成 utils/errorMonitor.ts：
   - 全局错误捕获：App.onError + Taro.onUnhandledRejection
   - 关键路径 try-catch：支付、登录、核心 API 调用
   - 错误上报：Sentry.init() 或自建接口，附设备信息、页面路径、堆栈
   - 脱敏处理：自动过滤手机号、身份证等敏感信息

3. 体验版发布流程 docs/release.md：
   - Step 1：代码上传（CI/CD 自动化或手动）
   - Step 2：设置体验版，添加测试成员
   - Step 3：内部测试 + bug 修复
   - Step 4：提交审核：隐私协议、测试账号、功能说明

4. 环境切换方案 config/env.ts：
   - dev/staging/prod 三套环境
   - API 域名白名单自动切换
   - 发布前强制检查：确认当前环境、域名白名单、AppID

5. 埋点验证脚本 utils/analytics-verify.ts：
   - 自动化发送测试埋点事件
   - 验证平台数据接收正常
   - 覆盖：page_view、click、conversion 三类核心事件
```

- **验收**：
  - iOS + Android 主流机型测试通过，无 Crash
  - 启动耗时 < 2s，内存 < 200MB，帧率 > 50fps
  - 异常监控上报正常，Sentry 面板可查
  - 体验版成功发布，测试成员可正常访问
  - 发布 Checklist 完整，审核材料齐全

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | Taro H5 + 微信开发者工具均可启动；4 页面路由正常；HTTP 封装完成；双端一致性 > 90% |
| D2 | Store 持久化与恢复正常；缓存工具类 TTL/LRU 功能完整；H5 与小程序缓存行为一致 |
| D3 | 静默登录 + Token 无感刷新完整闭环；分享/订阅功能正常；授权拒绝降级不阻塞核心功能 |
| D4 | 暗色/亮色主题一键切换；Design Token 覆盖完整；定制组件 Props 清晰、可复用 |
| D5 | 骨架屏过渡自然无跳动；流式打字流畅；虚拟列表 1000 条帧率 > 50fps；Lottie 动画流畅 |
| D6 | AI 生成组件可编译运行；还原度 > 90%；Prompt 模板 >= 5 个 |
| D7 | 主流机型测试无 Crash；启动 < 2s、内存 < 200MB；异常监控正常；体验版成功发布 |

## 最终验收标准

- 微信小程序在 iOS/Android 主流机型上运行流畅，内存 < 200MB，启动 < 2s
- 用户授权/Token 刷新无断点，静默登录体验无感
- UI 还原度 > 90%，暗色/动态主题切换正常，Design Token 体系完整
- 微交互打磨到位：骨架屏过渡自然、流式打字流畅、虚拟列表高性能、Lottie 动画丝滑
- AI 辅助组件生成流水线可复用，高频 Prompt 模板沉淀 >= 5 个
- 真机兼容性测试通过，体验版成功发布，审核材料齐全
- 异常监控与埋点体系完整运行

## 高频 Prompt 模板

1. **Taro 多端项目初始化 Prompt**
   - React/Vue3 + TypeScript 模板
   - weapp-tailwindcss 集成与尺寸适配
   - HTTP 请求层封装（拦截器、错误处理、重试）
   - 环境变量分离与构建脚本配置

2. **小程序持久化状态管理 Prompt**
   - Pinia/Zustand Store 设计
   - Storage 自动同步中间件
   - 三层缓存策略（Store/Storage/Filesystem）
   - TTL + LRU 过期淘汰

3. **微信授权/分享/订阅消息集成 Prompt**
   - 静默登录 + Token 无感刷新
   - 用户授权降级处理
   - 分享与订阅消息封装
   - H5 环境降级方案

4. **暗色/动态主题系统 Prompt**
   - Design Token 定义与 CSS 变量导出
   - ThemeProvider 运行时切换
   - 跟随系统主题
   - 平滑过渡动画

5. **微交互（骨架屏/流式动画/虚拟列表）Prompt**
   - 骨架屏多形状占位 + 渐隐过渡
   - 流式打字 + Markdown 实时解析
   - 虚拟列表 + 自动滚动优化
   - Lottie 动画集成

6. **Figma → Tailwind 组件生成 Prompt**
   - 结构化设计描述输入
   - Taro + Tailwind 代码输出
   - Props 接口定义 + 多状态覆盖
   - 还原度量化校验

7. **真机调试与发布流程 Prompt**
   - 双端机型兼容 Checklist
   - 异常监控（Sentry）集成
   - 体验版发布与审核准备
   - 环境切换与埋点验证

## 动态调整建议

- **前端经验丰富 / Taro 不熟悉**：Day 1 放慢节奏，重点熟悉 Taro 生命周期、条件编译与小程序特有 API；可同时探索 Uniapp 作为备选方案。
- **有 Figma 设计稿 / 无设计资源**：Day 6 可提前至 Day 1 并行，用 AI 辅助生成设计稿，缩短设计-开发周期。
- **有现成状态管理方案**：Day 2 可压缩至半天，重点放在持久化与缓存策略，状态管理模块直接复用。
- **无微信开放平台经验**：Day 3 为核心里程碑，优先跑通静默登录 + Token 刷新，分享/订阅可后续迭代。
- **有 H5 现成代码 / 纯前端迁移**：Day 1-2 聚焦 Taro 适配与小程序特有的 API 替换，组件逻辑直接复用。
- **交互要求不高 / 快速 MVP**：Day 5 可降级为骨架屏 + 基础滚动，虚拟列表与流式动画放在后续迭代。
- **追求极致性能**：Day 5 优先虚拟列表优化，Day 7 真机性能调优配合微信 Audits 面板定位长任务与内存泄漏。

## 第 7 天自测清单

- [ ] Taro 项目 H5 + 微信小程序双端构建成功，UI 一致性 > 90%
- [ ] 状态管理持久化正常，缓存分层策略生效，TTL 过期自动清理
- [ ] 静默登录 + Token 无感刷新完整闭环，授权/分享/订阅功能正常
- [ ] 暗色/亮色主题一键切换，Design Token 覆盖所有基础组件
- [ ] 骨架屏过渡自然，流式打字流畅不卡顿，虚拟列表 1000 条帧率 > 50fps
- [ ] AI 生成组件还原度 > 90%，高频 Prompt 模板 >= 5 个
- [ ] 真机双端测试无 Crash，性能指标达标（启动 < 2s、内存 < 200MB、帧率 > 50fps）
- [ ] 异常监控上报正常，关键埋点数据可查
- [ ] 体验版成功发布，审核材料齐全，发布 Checklist 完整
- [ ] 仓库包含：项目源码、HTTP 封装、缓存工具库、微信 API 封装、主题系统、组件库、Figma Prompt 模板、发布文档
- [ ] 能清晰口述小程序跨端构建、微信 API 集成与性能优化方法论
