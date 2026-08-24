# cue-buddy

**[English](README.md) · [中文](README.zh-CN.md)**

> 一个 AI agent skill,让业务专家通过对话起草、校验、测试、设为常用 [Cue](https://cuecue.cn) "搭子"调研模板——**不用写一行代码**。

> **兄弟 skill:** [`cue-research`](../cue-research) — 在你的 AI agent 里**用**搭子(问 → 匹配 → 确认 → 跑 → 可选沉淀)。cue-buddy 负责**做**搭子,cue-research 负责**用**。

## Cue 是什么 / 搭子是什么

[Cue](https://cuecue.cn) 是面向复杂金融与商业场景的 **Deep Research Agent + Intelligence Sentinel** 平台。后端从 **300+ 专业数据工具**(A 股/港股/美股披露 / 工商 / 司法 / 监管 / 资金流 / 行业研报 / 政府采购)里挑工具、多源交叉验证,**每个结论附来源链接**——把"在十个网站之间来回切半天"压到几分钟。

**"搭子"(buddy)** 是 Cue 里的专属调研伙伴:预先定义场景(对公授信预尽调 / 主体合规风险公开快照 / 季度财报点评 / 财富投顾对比 / 私募尽调 / 行业景气跟踪 等),把"满意的研究路径"沉淀成模板。之后只需输入主体名/重点,搭子按你定好的**调研策略**自动取证、按你定好的**报告骨架**自动产出结构化报告。Cue 的产品命题是"**把满意经历沉淀成你身边的 AI 伙伴**"——搭子模板就是这个沉淀的载体。

## 本 skill 做什么

`cue-buddy` 是一个能装进任意 AI agent(Claude Code / Codex CLI / Gemini CLI / OpenClaw 等)的 [skill](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills),把"对话"转化成 Cue 模板的起草动作。业务专家(不写 Python、不读 API spec)用业务语言跟 agent 说话;agent 起草、校验、创建、测试、调优、并设为常用(钉到工作台首页"常用"区),全程走 Cue 生产 API。

一个搭子模板由 **4 个 LLM-consumed 字段**组成:

- **`input_form_spec`** — 用户输入表单规范(必填变量 + 可填变量 + 默认值)
- **`goal`** — 简洁有力、价值优先的一段简介（搭子卡片文案）：解决什么问题 / 给什么价值 —— 不写角色代入、不堆实现细节、不硬码主体
- **`search_plan`** — 调研策略(按数据源聚类)
- **`report_format`** — 报告骨架(章节 + 每章执行蓝图)

创建后,搭子进入用户的 cuecue.cn 个人模板库,可跑真实调研任务(典型 **3–8 积分/次**,确切费用见工作台);**设为常用**后会钉到工作台首页"常用"区方便快速调用。

本 skill 把 author loop 做成业务用户能自助跑:

```
User: "我想做一个针对城商行客户经理的对公授信预尽调搭子"
Agent: [reads SKILL.md → triggers +author flow]
       → asks 4 groups of business questions
       → calls GET /api/tools/capabilities to inventory current Cue
         researcher surface (~391 tools / ~56 categories / 10 presets)
       → drafts the 4 fields via LLM, aligned to supported capability
         domains (category = supervisor routing label)
       → cross-checks each search_plan dimension against capabilities
         API; warns user if any declared evidence source has no
         backing category (some niche public-source dimensions may
         fall back to web_search)
       → runs +validate against 7 hard rules
       → on confirmation, POSTs to user's template library
       → optionally runs +test on a real case
       → on confirmation, +frequent 把模板钉到工作台首页"常用"区
```

> **范围边界(避免起 buddy 时踩坑)**:Cue 工具面**仅覆盖公开数据源**。需要**私有数据**的场景(银行真正反洗钱 AML 需内部交易流水 / 医疗诊断需电子病历 / 企业内账等)**不适合做成 Cue 搭子**——supervisor 在 catalog 里挑不到匹配工具,只能 web_search 兜底。`+author` 在起草时会调 `+capabilities` 交叉验证 search_plan 各维度,无 category 兜底时 warn 用户。

## 状态

**v0.3.6** — 当前版本（确切版本见 `SKILL.md` frontmatter）。cross-agent 已验证：详细写报告的那次（[`docs/verification-reports/2026-05-20-gemini-cli.md`](./docs/verification-reports/2026-05-20-gemini-cli.md)）是 v0.1.0 的 Gemini CLI 跑，正是它跑出 +test 长流断点、驱动了 replay fallback 加固（Claude Code + Codex CLI 同期一起验过）；v0.2.0 起有实活 cross-agent 跑（真实任务、live 生产 API），在 **Hermes、OpenClaw、Kimi** 等 agent 上。近版本：v0.3.3 与 cue-research 版本统一，v0.3.4 把运行时文件整合到单一可写根目录（`CUE_HOME`），v0.3.6 校验器强制业务语言输入。

## 适合谁用

- **业务专家**:金融 / 银行授信 / 资管投顾 / 私募尽调 / 合规监管研究 / 行业咨询(以公开数据可调研为前提)
- 懂场景但不写 Python、不读 API spec
- 有 Cue 账号([cuecue.cn](https://cuecue.cn) 注册)
- 有 API key([cuecue.cn/api-key](https://cuecue.cn/api-key) 创建)

如果你是开发者要把 Cue 集成到自有应用,**直接用 [Cue API docs](https://cuecue.cn)**;本 skill 是为非技术 author 优化的。

## Quickstart

### 1. 把 skill 装进 agent

Clone 本仓库(或 download 这个目录),让 agent load 它。

- **Claude Code**:放到配好的 skills 路径下,或用 `/skill cue-buddy` 调用(取决 CLI 版本)
- **Codex CLI**:`cat <path>/SKILL.md` 手动 load
- **Gemini CLI**:用 `activate_skill` 指 SKILL.md 路径
- **OpenClaw / 其他**:按各 agent 的 skill loading 约定

### 2. 配 API key(一次)

到 [https://cuecue.cn/api-key](https://cuecue.cn/api-key) 建 key,然后:

```bash
export CUE_API_KEY=sk...
```

或写 `~/.cue/config.json`:

```json
{ "api_key": "sk...", "base": "https://cuecue.cn/api" }
```

验证:

```bash
python3 scripts/cue_api.py whoami
```

### 3. 试跑

跟 agent 说想要什么就行:

```
"我想做一个高风险主体公开合规快照搭子"
"design a buddy for earnings-call quick reviews"
"基于这份样例报告 ./report.pdf 做一个尽调搭子"
"测一下我刚才那个搭子,主体用万科"
```

agent 读 SKILL.md 自动调相应 verb(`+author` / `+test` / `+tune` / `+frequent` 等)。

## 能做什么

| Verb | 说明 | 计费? |
|---|---|---|
| `+author` | 引导式 Q&A 起草 4 字段;调 `+capabilities` 跟 Cue 实际工具面对齐 + 漏覆盖 warn | 否 |
| `+capabilities` | 列 Cue researcher 工具面(~391 tools / ~56 categories / 10 presets);`q=<词>` / `category=<标签>` 探查;ETag 缓存 | 否 |
| `+validate` | 离线校验 JSON 模板对 7 条 hard rule 是否合规 | 否 |
| `+create` | 把校验过的模板 POST 到你的库 | 否 |
| `+list` | 列你的模板 | 否 |
| `+get` | 拉一个完整模板 | 否 |
| `+update` | 改已有模板 | 否 |
| `+test` | 跑一次真实对话,抓报告,跑 8 项验收 | **是**(~3–8 积分) |
| `+tune` | LLM 基于问题清单优化模板;diff 预览 + 提交前自动备份 | **是**(~1–3 积分) |
| `+frequent` | **设为常用** — 把模板钉到工作台首页"常用"区(`is_frequent=true`)。Cue 当前**没有跨用户发布**原语,这只是个人常用入口。 | 否 |
| `+unfrequent` | 取消"常用",从首页移除 | 否 |

详细 verb-by-verb walkthrough 见 [`SKILL.md`](./SKILL.md)。

## 隐私

你提供的参考资料（样例报告、内部 SOP、监控页面等）**只留在本机**。skill 只从中提取结构（章节大纲、来源聚类、语气）用于起草，**绝不会把你的原件上传给 Cue**。

agent 消费本地文件时的详细规则见 [`references/materials-intake.md`](references/materials-intake.md)。

## 仓库结构

```
cue-buddy/
├── SKILL.md                   # 调用方 agent 读取的 skill 规范
├── scripts/
│   ├── cue_api.py             # 仅标准库的 HTTP 客户端（零依赖）
│   ├── validate_template.py   # 离线 7 条 hard-rule 校验器
│   ├── test_template.py       # 跑真实对话 + 8 项参数化验收
│   └── tune_template.py       # 生成-修订 + diff 预览 + 确认 + 自动备份 + PUT
└── references/
    ├── template-fields-spec.md     # 4 字段详细格式指南
    ├── hard-rules.md               # Validator 规则 R1–R8 及设计理由
    ├── materials-intake.md         # agent 如何消费用户提供的本地文件
    └── examples/
        └── corporate-credit.md     # 完整样例模板（实测可用）
```

## 依赖

- Python 3.10+（仅标准库——无需 `pip install`）
- 支持 skills 的 AI agent

## 贡献

Issue 和 PR 都欢迎。特别有价值的:

- 新 `references/examples/<scenario>.md`:对照 Cue 工具面的场景模板(财报点评 / 私募尽调 / 公开合规快照 / 政府采购线索 / 政策跟踪 / 行业景气 等)——scope 要跟 Cue 实际 surface(finance / 工商 / 司法 / 监管 / 资金流 / 行业研报 / 政府采购)对齐,**避开需要私有数据的场景**(银行内部 AML / 医疗诊断 等)
- 跨 agent verification report(Codex / Gemini / OpenClaw)
- 基于失败模式证据的新 hard-rule 提案

## License

MIT — 见根目录 [LICENSE](../LICENSE)。
