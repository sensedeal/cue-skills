---
name: cue-buddy
description: "Use when the user wants to author / validate / debug / test / tune / pin-as-frequent a Cue 搭子(buddy) research template for a recurring scenario (corporate-credit pre-diligence, compliance snapshot, earnings review, private-fund DD, etc.) via natural conversation. Triggers: 创建搭子 / 做一个 X 搭子 / 调试模板 / 测试我的搭子 / 提交模板 / 设为常用 / design a buddy for X / mark template as frequent. Public-data tool surface only — refuse for private-data scenarios (real AML / medical diagnosis / internal accounting)."
license: MIT
metadata:
  version: "0.2.0"
  requires:
    bins: ["python3"]
    envOptional: ["CUE_API_KEY", "CUE_API_BASE"]
  endpoints:
    base: "https://cuecue.cn/api"
    apiKeyPage: "https://cuecue.cn/api-key"
---

# cue-buddy — 搭子模板作者工具

让业务用户在自己的 AI agent 里**起草、校验、创建、调试**搭子模板，并提交到 cuecue.cn 个人模板库。无需写代码，全程通过 Cue 生产 API 完成。

## Cue 是什么 / 搭子是什么

[Cue](https://cuecue.cn) 是面向复杂金融与商业场景的 **Deep Research Agent + Intelligence Sentinel** 平台——后端能从 **300+ 专业数据工具**（A 股/港股/美股/基金/工商/司法/监管/研报/资金流...）里主动挑工具、多源交叉验证，**每个结论附来源链接**——把"在十个网站之间来回切半天"的体力活压到几分钟。

**一个"搭子"是 Cue 里的专属调研伙伴**:把"满意的研究路径"沉淀成模板,**反复用于同类场景**(对公授信预尽调 / 主体合规风险公开快照 / 季度财报点评 / 财富投顾对比 / 私募尽调 / 行业景气跟踪 / 政府采购线索分析 ...)。之后只需输入主体名/重点,搭子按 Cue 实际工具面(A 股/港股/美股 / 基金 AMAC / 工商 / 司法 / 监管 / 资金流 / 行业研报 / 招投标 等公开数据)自动取证、按你定好的**报告骨架**自动产出结构化报告。Cue 的产品命题是"**把满意经历沉淀成你身边的 AI 伙伴**"——搭子模板就是这个沉淀的载体。

> **重要心智模型**:**Cue 公开搭子库已经有 100+ 个常见场景的搭子**,任何账号都能立刻调用——**一次性、不重复的调研不需要先建搭子**(去 [cuecue.cn](https://cuecue.cn) 网页端或兄弟 skill [`cue-research`](../cue-research) 直接说"调研 X"即可)。**本 skill (`cue-buddy`) 是给"你有一类反复要做的场景、想沉淀成专属搭子"的人用的**——一次起草、长期复用。

> **agent 首次跟用户对话时,默认认为用户库非空**(系统公开搭子 100+ 任何账号都能用),**不要暗示"必须先 +create 才能跑调研"**;不确定时调 `search_templates(keyword="", include_system=True)` 看真实状态。

> **范围边界(避免起 buddy 时踩坑)**:Cue 工具面**仅含公开数据源**。需要**私有数据**的场景(如真正反洗钱 AML 需银行内部交易流水、医疗诊断需电子病历、税务尽调需企业内账)**不适合做成 Cue 搭子** — supervisor 在 catalog 里挑不到匹配工具,只能 web_search 兜底,失去 Cue 调研伙伴价值定位。
>
> **`+author` 的两档防护**:
> 1. **Hard refusal** — 当用户明确说"反洗钱 AML / 医疗诊断 / 内账尽调"等需要 **私有数据** 的场景时,agent **拒绝起草**,提示"Cue 公开数据面不支持此场景,建议改写为 X(公开监管+司法+处罚数据)" — 让 author 要么换形态,要么知难而退。
> 2. **Soft warn** — 当 search_plan 单个维度无 category 兜底(如"行业协会公开数据"现 catalog 无对应 tool),`+author` 流程 warn 用户该维度只走 web_search 兜底,可继续 create。

本 skill 的产物就是定义这个调研伙伴的 **4 个字段**：

| 字段 | 决定 | ⚠️ 常见误解 |
|---|---|---|
| `title` | 搭子在卡片上的**名字** | 简洁有力、体现价值（~≤8-10字）；砍虚词（公开/全量/细项/与分析/简报/深度），但**别过度简化丢掉区分价值**（信披属实/需求匹配/海外执法 这类要留） |
| `input_form_spec` | **用户输入表单规范**（必填/可填变量 + 默认值） | 单行 `需提供: [属性_主体_类型]，可提供: [属性_主体_类型] (默认: ...)`，前端把 `[...]` 渲染成输入框。**不是**自由文字介绍 |
| `goal` | 搭子简介=卡片文案：解决什么问题/给什么价值 | 简洁有力一段（~40-80字，价值优先）；不堆"怎么做"、不泄漏实现、不硬码主体、不写免责、不写编号清单 |
| `search_plan` | 你按哪些数据源、用什么策略取证 | 按"数据来源"聚类，不按章节顺序线性走 |
| `report_format` | 你交付什么样的报告（章节/蓝图） | 主标题必须含三段式变量，每章带 `[执行蓝图]` 块 |

后端按顺序消费这 4 字段：先按 `input_form_spec` 表单收输入 → 按 `search_plan` 调研取证 → 按 `report_format` 产报告；整段产出由 `goal` 定基调。

"搭子描述/介绍"这类自由文字其实只在前端工作台分类卡片上展示一句话——那是后端从 `goal` 自动派生的，**作者不需要单独写**。

## 你是谁、做什么

- **目标用户**：懂业务场景（金融 / 银行授信 / 资管投顾 / 私募尽调 / 合规监管研究 / 行业咨询 等专业领域,以公开数据可调研为前提）的非技术人员
- **能做**：用自然语言描述一个场景、**或者把你工作中的样例报告 / 行业 SOP / 监管文件 / 相关链接喂给 agent**，让本 skill 引导你把它们整理成符合 Cue 模板规范的 4 个字段、提交到你的模板库、并跑真实任务验证
- **不需要懂**：Python / API / BuddyContract 等技术概念。本 skill 把这些藏起来，你只见业务语言
- **隐私边界**：你提供的本地材料只在你 agent 的上下文里使用，**不会被上传到 Cue 服务端**（详见 [`references/materials-intake.md`](references/materials-intake.md)）

## Onboarding(给 agent 的指令——首屏怎么说)

**禁止行为**:第一屏**不要列完整 verb 菜单**(`+author / +list / +capabilities / +test / +tune ...` 等),也**不要单独把 `+capabilities` 推给用户**——那是给开发者看的内部 verb,业务用户永远用不上。

**首屏应该说什么**:

1. **一句温和的招呼**(1 行,认出他到了哪)。
2. **意图分流(2 选 1,自然语言,带 brief 说明)**:
   > 你今天想做什么?
   > 1. **有反复要做的某类调研场景**,想做个自己的搭子(几分钟搞定;之后这类问题都用它跑) → 我引导你
   > 2. **就想立刻调研一下某个公司/话题**(一次性) → 用兄弟 skill [`cue-research`](../cue-research)(按你 agent 的加载方式启用),或直接去 [cuecue.cn](https://cuecue.cn) 网页端;**不用先建搭子**,系统公开搭子 100+ 任何账号都能跑
3. **一行隐性提醒**:跑真任务花积分(粗略 3-8 积分 起步,跑前必有确认);只看公开数据(私有数据场景如银行流水/病历/内账会被拒)。
4. **停**。等用户回答。**不要塞 `+author` / `+ask` / 完整 verb 列表 / 详细 step**。

**可选快捷词**(用户主动输才用,不要主动展示):用户如果直接输 `+author` 或 `+ask`,agent 识别为明确触发即可走对应流。**默认还是自然语言路由**(下面的"决策树"是你内部参考,不是给用户看的菜单)。

**首屏数据保护**:agent 不要在第一屏调任何**会消耗 credits 或写库**的 API。若需要看用户库状态(用户问"我有什么搭子可用"),调 `search_templates(keyword="", include_system=True)` 拿真实情况(免费、只读),**不要凭空假设空库或非空库**。

## 一份"搭子"由 4 个朴素回答组成

| 问题 | 字段名 | 例子 |
|---|---|---|
| 用户给你什么输入？ | `input_form_spec` | "需提供：[目标_授信_企业]，可提供：[关注_风险_主题] (默认：通用授信审查)" |
| 你是谁、要解决什么痛点？ | `goal` | "作为银行客户经理的预尽调助手，从公开监管披露和司法记录穿透 [目标_授信_企业] 的偿债与合规风险..." |
| 你怎么调研？（按数据来源分组） | `search_plan` | 主体核验 / 财务实证 / 行业景气 / 经营动态 4 个聚类，每个写明数据路由+执行动作+验证策略 |
| 报告交付什么样？ | `report_format` | `> **关键配置**` 头部 + 13 个章节，每节带 `> **[执行蓝图]**` 块（研究目标/逻辑链条/信息需求/输出形式） |

详细字段规范见 [`references/template-fields-spec.md`](references/template-fields-spec.md)。规则铁律见 [`references/hard-rules.md`](references/hard-rules.md)。

## 准备：API key 一次性配置

1. 打开 `https://cuecue.cn/api-key`（已登录 Cue 账号）
2. 创建一个 API key（格式 `sk...`），复制
3. 在 shell 里设置环境变量（一次即可）：

```bash
export CUE_API_KEY=sk...
```

或写入 `~/.cue/config.json`：

```json
{ "api_key": "sk...", "base": "https://cuecue.cn/api" }
```

可选：`export CUE_API_BASE=https://cuecue.cn/api`（覆盖默认）。

调用任何 verb 前 skill 会自动校验 key 可用（请求 `/api/templates`，200 即过）。

## 调用约定（verbs）

所有操作通过 `+<verb>` 触发。Skill 通过本目录下 `scripts/` 里的 Python 脚本（仅 stdlib，无依赖）执行。

| Verb | 做什么 | 是否消耗 credits | 后端 endpoint |
|---|---|---|---|
| `+author` | 引导式起草新模板：问几个业务问题 → 调 `+capabilities` 拿当前 Cue 工具面 → agent LLM 按支持的 category 起草 4 字段 → 跑 `+capabilities` 交叉验证 search_plan 各维度有 category 兜底（无则 warn）→ 自动跑 `+validate` | 否（capabilities 是只读 metadata，不计费） | (本地 + `GET /api/tools/capabilities`) |
| `+capabilities` | 拉当前 Cue researcher 工具面（~391 tools / ~56 categories / 10 presets）；支持 `q=<关键词>` / `category=<标签>` 探查;ETag 缓存 + 304 短路;不带参数返 summary | 否 | `GET /api/tools/capabilities` |
| `+validate <file>` | 离线校验任意 JSON 模板文件是否合规 | 否 | (本地) |
| `+create` | 把校验过的模板 POST 到你的模板库 | 否 | `POST /api/templates` |
| `+list` | 列出你的所有模板 | 否 | `GET /api/templates` |
| `+get <template_id>` | 拉取一个完整模板 | 否 | `GET /api/templates/<id>` |
| `+update <template_id>` | 修改已有模板 | 否 | `PUT /api/templates/<id>` |
| `+test <template_id> <entity>` | 跑一次真实对话（例如以"万科"做测试主体），抓 SSE 流，跑 8 项参数化验收。**单次深研通常 3-15 分钟，复杂主体更久；服务端 60 分钟硬超时**——客户端等待应按此设置（`--timeout` 默认 3600s），超时后走 DB 回放兜底、不重复扣费 | **是**（粗略 **3-8 积分** 起步，确切费用见工作台） | `POST /api/chat/stream` |
| `+tune <template_id> --issues <path>` | 基于当前内容 + 问题清单让 LLM 优化模板（走 seed: bypass 路径），含 diff 预览与人工确认 | **是**（粗略 **1-3 积分** 起步） | `POST /api/generate_template` + `PUT /api/templates/<id>` |
| `+frequent <template_id>` | 把模板设为"常用",钉到 cuecue.cn 工作台首页"常用"区 | 否 | `POST /api/templates/frequent` |
| `+unfrequent <template_id>` | 取消"常用",从首页"常用"区移除 | 否 | `POST /api/templates/frequent` (`is_frequent=false`) |
| `+upgrade` | 检查并(经确认后)升级 skill 自身到 GitHub `main` 最新版。git clone 装的走 `git pull --ff-only`,copy 装的给手动指引;本地有未提交改动则 abort 不强覆盖。**注意:跟 `+update <template_id>`(改模板)语义完全不同** | 否 | (GitHub raw + `git pull`,**本地操作**) |

**全部已上线 verb**:`+author / +capabilities / +validate / +create / +list / +get / +update / +test / +tune / +frequent / +unfrequent / +upgrade`。

**`+upgrade` 与 session 启动 silent-check**:agent 加载本 SKILL.md 时,**建议**在跑任何 verb 前先 silent 跑一次:`python3 cue-buddy/scripts/update_skill.py --silent-check`。这是带 24h 冷却的轻量版本对比,落后时只在 stderr 打一行 `ℹ️ cue-skills/cue-buddy 有新版可用 vX → vY,运行 +upgrade 升级`,**不弹问、不阻塞、不自动 pull**。网络失败时静默跳过(下次再试)。冷却 timestamp 存 `~/.cue/last-update-check.json`。

**关于 `+frequent` 不叫 `+publish`**:Cue 当前没有"跨用户发布"原语;`+frequent` 实际就是把模板钉到调用者自己工作台首页"常用"区(`is_frequent=true`)方便高频访问。早期文档曾用 `+publish` 命名容易让用户误以为是对外发布——已统一改名为 `+frequent`。"对外分享"能力须走 cuecue.cn 网页端的分享/复制链路。

## 决策树（agent 怎么响应用户）

中英文都识别；下面给典型短语，agent 应识别语义而非死匹配字符串。

```
用户说什么（中/英文/口语）                                       → 调哪个 verb
──────────────────────────────────────────────────────────────────────────
"创建一个搭子" / "做一个 X 场景的搭子" / "我想做一个 X 助手"      → +author
"design a buddy for X" / "make me a buddy" / "I want to build"   → +author
"启动 X 场景搭子设计"                                            → +author

"我有个模板想检查格式" + 文件路径 / "lint this template"          → +validate
"建到我的模板库" / "保存"(after +author) / "save this" / "提交"   → +create
"看看我有哪些模板" / "list my buddies" / "我的模板"               → +list
"看下 tpl_xxx 的内容" / "show me tpl_xxx" / "fetch X"             → +get <id>
"改 tpl_xxx 的 input_form_spec" / "update <id>" / "改一下 X 字段"    → +update <id>

"跑一下 tpl_xxx 测试" / "测一下 X 主体" / "test with 万科" /
 "run a test on X" / "用 X 验证"                                  → +test
"自动优化 tpl_xxx" / "根据问题改一下" / "tune this" / "调优"      → +tune
"设为常用 tpl_xxx" / "钉到首页" / "mark frequent" / "pin to home"  → +frequent
"取消常用 tpl_xxx" / "从首页摘掉" / "unpin" / "unfrequent"         → +unfrequent

"升级 skill" / "更新 cue-skills" / "更新 cue-buddy" / "check for skill updates" / "拉一下最新版" → +upgrade
(注意:"改 tpl_xxx" / "更新模板 X" 等带 template_id 的语义走 `+update <id>`,**不是** `+upgrade`)
──────────────────────────────────────────────────────────────────────────
```

### Reference doc 读取路由（机械化）

不同流程阶段必须读不同的 references doc，不要凭印象起草：

| 时机 | 必读 doc |
|---|---|
| `+author` Stage 0 — 用户提供材料 | [`references/materials-intake.md`](references/materials-intake.md) |
| `+author` Stage 1-4 — 起草 4 字段 | [`references/template-fields-spec.md`](references/template-fields-spec.md) |
| `+validate` 返回 errors / 用户说"为什么报错" | [`references/hard-rules.md`](references/hard-rules.md) |
| `+author` 首次启动需要示例参考 | [`references/examples/corporate-credit.md`](references/examples/corporate-credit.md) |

## `+author` 流程（最常用）

Agent 引导用户回答 4 组问题，对应 4 个字段。每个问题先用业务语言问，再 agent LLM 起草字段内容，立即跑 `+validate` 反馈。

### Stage 0：参考材料摄入（强烈建议）

在问字段问题前，agent 先问用户：

> "你手头有没有这个场景下的参考资料?可选类型:已有报告样例(PDF/Word/Markdown/纯文本)、行业 SOP/内部规范/监管文件、同类竞品搭子描述、相关链接(公司官网/行业研报/监管页面)。
>
> 1. 我有文件,路径给你
> 2. 我有链接,贴给你
> 3. 我直接粘文本
> 4. 没有,直接起草(凭场景描述起,无参考)"

(1/2/3 可叠加——例如先粘链接再补充文本。)

Agent 用 `Read` / `WebFetch` 读取后，**只在本地 agent 上下文里使用**——绝不上传到 Cue API、绝不写进任何 `+create / +update` 的 payload，绝不入 git。

从材料里提取：
- 章节结构 → 反推 `report_format` 的 13 节骨架
- 字段口径 / 行业术语 → 校准 `goal` 与 `search_plan` 的用词
- 数据源命名 → 校准 `search_plan` 的数据路由聚类
- 报告基调（克制 vs 强观点 / 长 vs 短）→ 写进 `关键配置 · 基调设定`

具体提取规则见 [`references/materials-intake.md`](references/materials-intake.md)。

### Stage 1-4：4 字段引导起草

1. **场景与角色**
   - 你的目标用户是谁?(例如:银行授信岗、券商投研、私募尽调、主体合规公开快照、政府采购线索分析)
   - 这个搭子要解决用户什么具体痛点?
   - 起点选哪个?
     > 1. 参考已有示例(`references/examples/corporate-credit.md` 是金融预尽调,做对公授信类直接拷裁剪)
     > 2. 从零起(我描述场景,你起草)
     > 3. 我先描述场景,你帮我从 `references/examples/` 里推荐最匹配的示例
   → 起草 `goal` + `title` + 类别

2. **输入定义**
   - 用户必填什么？（例如：企业名 / 病例编号 / 行业关键词）
   - 可选输入哪些？（例如：时间窗口 / 关注重点）
   - 必填变量起个三段式名字：`[属性_主体_类型]`（skill 帮你命名）
   → 起草 `input_form_spec`

3. **调研策略**
   - 你的搭子从哪些**公开数据来源**取证据?(公开披露 / 司法数据库 / 行业报告 / 新闻舆情 等)
   - 把数据源按"一次拉取多类信息"的方式聚类成 2-5 个调研维度
   - ⚠️ **本地材料**(用户提供的样例报告 / 内部规范 / 监管文件)只用作起草模板**结构**的参考——它们**不是 Cue 运行时能抓取的数据源**,不要写进 search_plan 的"数据路由"
   - 每个维度写明：支撑报告哪些章节 / 怎么执行 / 怎么验证多源冲突
   → 起草 `search_plan`

4. **输出形态**
   - 报告有多少章节？每章解决什么问题？
   - 每章读者读完应该获得什么决策依据？
   - 章节顺序应该是怎样的？（结论先行 / 时间线 / 风险等级…）
   → 起草 `report_format`，每章带 `[执行蓝图]` 块

每步起草后立即 `+validate`，发现规则违反就当场改。

## Hard Rules（铁律，违反会被 `+validate` 拒绝）

完整版见 [`references/hard-rules.md`](references/hard-rules.md)，最重要的 5 条：

1. **`input_form_spec` 必须三段式变量** — `需提供: [属性_主体_类型]，可提供: [属性_主体_类型] (默认: ...)` 单行
2. **`goal` 必须简洁有力、价值优先**（它就是卡片简介）— ~40-80字一段，讲解决什么问题/给什么价值；不堆怎么做（放 search_plan）、不泄漏实现、不硬码主体、不写免责、不写编号清单（详见 hard-rules R2）
3. **`search_plan` 必须按"数据来源"聚类** — 而不是按章节顺序线性走
4. **`report_format` 主标题必须含变量** — `# [目标_<场景>_主体] <场景>底稿`，不要写死字符串
5. **任何字段不准出现工具名**（`get_*` / `list_*` / `find_*` 等开头），也不准出现"建议进入/谨慎进入/暂缓进入"等决策语 — 搭子是证据收集器，不是决策者

## 示例模板

- [`references/examples/corporate-credit.md`](references/examples/corporate-credit.md) — 对公授信预尽调（金融/银行场景）
- [`references/examples/earnings-review.md`](references/examples/earnings-review.md) — 季度财报点评（二级投研场景）
- 后续将补充:主体合规风险快照、市场异动快讯、政府采购线索 等

## 安全规则

- API key 绝不出现在文本输出 / 提交的代码 / 日志里
- **如果用户不慎在对话里粘了 `sk...` 形式的 key**：立即提醒用户 (1) 不要再发，(2) 到 cuecue.cn/api-key 立即轮换该 key（之前那一份要废掉）。Agent 在后续对话中绝不复述/打印那段字符
- **用户提供的本地材料只在 agent 上下文中使用**，绝不上传到 Cue API、绝不写进 `create / update` payload、绝不入 git
  - "材料"定义见 [`references/materials-intake.md`](references/materials-intake.md) → "材料 的明确定义" 段
  - 如材料含敏感字段（客户名 / 内部金额 / 内控规则），抽取结构后明确告知用户"已用作模板起草，原文未上传"

### `+create` / `+update` 前的预检 checklist

Agent 在调用 `+create` / `+update` **之前必须自检**以下 4 项；任一项异常立刻问用户确认：

1. **payload 中的 `goal / input_form_spec` 段不含真实客户名、案号、金额、内部规范摘录** —— 这些都是材料，应替换成三段式变量或通用术语
2. **payload 中的 `search_plan` 没把任意"用户提供的样例报告原文段落"逐字 copy-paste 进去** —— 应抽取的是结构（信源/动作/验证），不是原文
3. **payload 中的 `report_format` 没夹带任何客户专属术语** —— 主标题已含三段式变量，没漏写死的客户名
4. **`source_conversation_id` 填的是 `seed:<slug>:v1` 或来自 +author 流程的 conv id**，不是任何真实业务对话 ID

通过后再 POST。

- `+create` / `+update` / `+frequent` / `+unfrequent` 等**写操作**前,用户必须明示确认。统一 1/2 风格,便于用户用数字回复:
  > 1. 确认执行
  > 2. 取消
- `+test` / `+tune` **消耗 credits 的操作**前,先提示"这次约消耗 N credits" 再用同款 1/2 确认。
- 删除操作（`+delete`）暂未实现，避免误删

## 兼容性

| Platform | 状态 | 调用方式 |
|---|---|---|
| Claude Code | ✅ 已验证 | 把目录加入 skills 路径，通过 `Skill` 工具自动加载 SKILL.md |
| Gemini CLI | ✅ 已验证(2026-05-20,见 [verification report](docs/verification-reports/2026-05-20-gemini-cli.md)) | `activate_skill` 加载 SKILL.md |
| Codex CLI | ✅ 已验证(2026-05-21) | 手动 `cat SKILL.md` 注入或按 codex skill 约定加载 |
| Hermes / OpenClaw / Kimi | ✅ 已验证(v0.2.0,真实任务跑通 live API) | 按各自 skill spec 加载 SKILL.md + scripts/ 目录 |
| 其他 agent | ⚠️ 未独立验证 | 按各自 skill spec 加载 SKILL.md + scripts/ 目录 |

scripts/ 用 Python 3.10+ stdlib，无第三方依赖，任何能跑 Python 的环境都通。如果你在 ✅ 之外的 agent 上跑通，欢迎到 GitHub repo 开 issue 报告兼容性。

## 关于 API 稳定性

Cue 公开 API 文档当前覆盖 4 个 endpoint：`POST /api/chat/stream`、`GET /api/templates`、`POST /api/templates/search`、`GET /api/templates/conversation/<id>`。

本 skill **额外使用**了若干内部 endpoint：`POST /api/templates`（create）、`PUT /api/templates/<id>`（update）、`GET /api/templates/<id>`（get one）、`POST /api/generate_template`（+tune 后端）、`POST /api/templates/frequent`（+frequent）。这些 endpoint 与前端工作台共享同一套 auth 中间件，API key 可调用，但**未列在公开 API 文档中**——意味着未来可能调整 path/payload。

如果你在 +create / +update / +tune / +frequent 上遇到 4xx 错误，先检查 [Cue 官方文档](https://sensedeal.feishu.cn/wiki/NS0ywPa4jiN4dgkA8V7cQvpxndf) 是否已更新对应规范。

## 脚本到 verb 映射

agent 不需要"硬编码"如何执行 verb——直接调用脚本即可：

| Verb | 脚本 | 等价命令 |
|---|---|---|
| `+validate <path>` | `validate_template.py` | `python3 scripts/validate_template.py path.json` |
| `+list` | `cue_api.py` | `python3 scripts/cue_api.py list` |
| `+get <id>` | `cue_api.py` | `python3 scripts/cue_api.py get <id>` |
| `+create` | `cue_api.py` | `python3 scripts/cue_api.py create payload.json` |
| `+update <id>` | `cue_api.py` | `python3 scripts/cue_api.py update <id> payload.json` |
| `+test <id> <entity>` | `test_template.py` | `python3 scripts/test_template.py <id> <entity> --save run.md` |
| `+tune <id> --issues f` | `tune_template.py` | `python3 scripts/tune_template.py <id> --issues issues.txt` |
| `+frequent <id>` | `cue_api.py` | `python3 scripts/cue_api.py frequent <id>` |
| `+unfrequent <id>` | `cue_api.py` | `python3 scripts/cue_api.py unfrequent <id>` |
| `+upgrade` | `update_skill.py` | `python3 scripts/update_skill.py --skill cue-buddy`(交互);`--silent-check` 走 session-start 轻量版 |

`+author` 没有专用脚本——它就是 agent 用 SKILL.md 的引导问答 + `validate_template.py` 反馈 + `cue_api.create_template` 落库的一个流程。
