# cue-skills

**[English](README.md) · [中文](README.zh-CN.md)**

[Cue](https://cuecue.cn)（sensedeal）官方开源 agent skills 集合。

**skill** 是一份可移植的指令包,任何 AI agent（[Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills) / Codex CLI / Gemini CLI / OpenClaw 等）都能 load 它来获得新能力——无需改 agent 本身。这个仓库收纳 Cue 对外维护的 skills。

## 仓库内 skill 列表

| Skill | 用途 | 状态 |
|---|---|---|
| [`cue-buddy/`](./cue-buddy) — **cue-buddy** | 让业务专家通过自然对话起草、校验、测试、调优、设为常用 [Cue](https://cuecue.cn) 搭子（buddy）调研模板。不需要 Python / 不需要懂 API；agent 替用户调 Cue 生产 API。 | v0.2.0 |
| [`cue-research/`](./cue-research) — **cue-research** | cue-buddy 的兄弟 skill,负责在你自己的 AI agent 里**用** Cue：自然语言提问 → 匹配 ≤2 个候选搭子(或走 `/api/rewrite` 自由式深研) → 确认 credits → 后台跑、replay 取报告 → 满意可一键沉淀为搭子(回流给 cue-buddy)。支持仿写/mimic(模仿参考链接或样本文档的写作风格)。 | v0.3.0 |
| [`playbook/`](./playbook) — **playbook 场景 skills** | [Cue 搭子广场](https://cuecue.cn/playbook)每个场景一个可供 agent 加载的 `SKILL.md`(投资研究 / 信贷尽调 / 财富投顾 / 全球宏观 …)。加载后你的 agent 就能跑该场景的 Cue 深度研究:运行时查 **live** `/api/playbook` 取该场景**当前**搭子 → 选一个 → 确认 credits → 跑 → 返回带来源报告。**运行时查 live、不烤 `template_id`**,搭子增删改自动反映、无需重生成。由 [`scripts/gen_scene_skills.py`](./scripts/gen_scene_skills.py) 自动生成;实际运行委托 `cue-research`(两者需同级并装)。 | 自动生成 |

Cue surface 扩展会陆续在这里加新 skill。

## Cue 是什么 / 搭子是什么

[Cue](https://cuecue.cn) 是面向高精度金融与商业场景的 **Deep Research Agent + Intelligence Sentinel** 平台。从 300+ 专业数据源（A 股/港股/美股披露 / 工商 / 司法 / 监管 / 资金流 / 行业研报 / 政府采购）里挑工具、多源交叉验证,几分钟产出带源引用的结构化报告——不杜撰、可回查。

**"搭子"** 是一份针对具体场景的调研 playbook——对公授信预尽调 / 主体合规风险公开快照 / 季度财报点评 / 私募尽调 等——定义一次,之后给个主体名就跑完。本仓库的 `cue-buddy` skill 就是让业务专家**用对话** author 这些 playbook 的工具。

详细 walkthrough:[`cue-buddy/README.zh-CN.md`](./cue-buddy/README.zh-CN.md)。

> **范围边界**:Cue 工具面仅覆盖**公开数据源**(上市公司披露 / 工商登记 / 司法公开 / 监管处罚 / 资金流向 等)。需要**私有数据**的场景(银行真正反洗钱 AML 需内部交易流水 / 医疗诊断 / 企业内账)**不适合做 Cue 搭子**——supervisor 路由不到匹配工具,只能 web_search 兜底。`cue-buddy +author` 在起草时会调 `+capabilities` 交叉验证每个 search_plan 维度,无 category 兜底时 warn 用户。

## 如何使用 skill

`cue-buddy` 是 self-contained:入口 `SKILL.md` + 支持的 `references/` + stdlib-only `scripts/`。`cue-research` **自己没有运行时脚本**——复用 cue-buddy 的(`cue_api` / `sse_report`),因此必须与 `cue-buddy` **同级目录并装**。

**Claude Code**:把 skill 文件夹 copy 到 `~/.claude/skills/`,或用 `/use-skill <path>` 引用。具体安装看 skill 自己的 README。**装 `cue-research` 时,把 `cue-buddy` 装在它旁边**(同一父目录),共享脚本才能被找到。

**其他 agent**:把 `<skill>/SKILL.md` 当 system instruction load。skill 的脚本尽量 stdlib-only。

**`playbook/`** 场景 skill 把实际跑研究委托给 `cue-research` 的 runner,后者又复用 `cue-buddy` 的脚本——所以要把三者(`playbook/<场景>`、`cue-research`、`cue-buddy`)装在同一父目录下作兄弟目录。

> **有免费积分可试**:每个 Cue 账号都送免费积分——**首次注册 50 分,之后每天再免费 10 分**。所以只要申请 API key(用 `cue` CLI 登录),就能先用免费额度跑深度研究、不花钱也能试。每次深度研究仍会消耗积分;skill 跑之前都会先跟你确认再花。

## 贡献

Bug / skill 建议:[开 issue](https://github.com/sensedeal/cue-skills/issues)。

欢迎 PR。每个 skill 有自己的 hard-rules / validator;贡献指引看具体 skill 的 README。

## License

MIT — 见 [LICENSE](./LICENSE)。skill 内容可自由使用、修改、再分发。
