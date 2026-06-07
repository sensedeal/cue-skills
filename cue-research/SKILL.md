---
name: cue-research
description: "Use when the user asks a research question they want Cue to run — against a saved 搭子(buddy) template or as free-form deep research. Triggers: 帮我查/调研/研究 + 主体或话题; ask Cue about X; 用 Cue 跑一下 Y; 看看哪个搭子能查 X; 把刚才那次调研存成搭子. Public-data scope only — refuse for private-data scenarios (real AML / medical / internal accounting)."
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

# cue-research — 让 Cue 在你的 agent 里直接干活

让你在自己的 AI agent 里**用自然语言把一个调研问题交给 Cue**：自动从你的搭子库里匹配 ≤2 个候选(或无合适搭子时改走"带后端 rewrite 的自由式深研")，确认 credits 后执行，跑完满意可以一键沉淀为搭子。本 skill 是 [`cue-buddy`](../cue-buddy) 的兄弟 skill——cue-buddy 负责**做**搭子，cue-research 负责**用**搭子。

## 范围边界(避免起调用前踩坑)

Cue 工具面仅含**公开数据源**(工商/司法/监管/财报/资金流/招投标等)。需要私有数据的场景(真·反洗钱看银行流水、医疗诊断、企业内账)agent **拒绝执行**，提示用户改写成公开数据形态或去 cuecue.cn 网页端。

## 准备

**依赖**:本 skill 没有自带运行时脚本,所有原语从 sibling `../cue-buddy/scripts` 导入(见下文"导入约定")。因此 **`cue-buddy` 必须与本 skill 同级目录并装**(例如都在 `~/.claude/skills/` 下)——只装 cue-research 会在 import 时失败。

跟 cue-buddy 共用一套 API key 配置(`CUE_API_KEY` env 或 `~/.cue/config.json`)。详见 [`../cue-buddy/SKILL.md`](../cue-buddy/SKILL.md) 的"准备"段。

## 调用约定(verbs)

| Verb | 做什么 | 耗 credits |
|---|---|---|
| `+ask <问题>` | 主入口：解析 → 匹配 ≤2 个搭子 → 用户选 1/2/0/n → 跑 → 交付 → 可选沉淀。**也接受隐式自然语言触发** | 跑前显式确认；不跑不收 |
| `+match <问题>` | 只匹配候选搭子，不跑 | 否 |
| `+rewrite <问题>` | 只调 /api/rewrite 看 user_confirmation + rewritten_mandate，不跑 | 否 |
| `+save <conversation_id>` | 把一次成功的 free-form 跑沉淀为搭子(handoff 给 cue-buddy 的 +author/+create) | 否(模板生成本身不消耗，跑测试才会) |
| `+upgrade` | 检查并(经确认后)升级 skill 自身到 GitHub `main` 最新版。git clone 装的走 `git pull --ff-only`,copy 装的给手动指引。session 启动时 agent 应 silent 跑 `update_skill.py --silent-check --skill cue-research`(24h 冷却,落后时只在 stderr 打一行,不弹问) | 否 |

## 决策树

```
用户说什么(中/英文/口语)                                              → 走哪条
─────────────────────────────────────────────────────────────────────────
"帮我查/调研/研究 <主体或话题>"                                       → +ask
"ask Cue about X" / "用 Cue 跑一下 Y"                                  → +ask
"看看哪个搭子能查 X"(只匹配不跑)                                       → +match
"先帮我把这个问题改写成结构化的(不跑)"                                 → +rewrite
"把刚才那次调研存成搭子" / "save this run as a buddy"                  → +save
"更新一下 skill" / "check for updates" / "升级搭子工具本身"            → +upgrade
─────────────────────────────────────────────────────────────────────────
```

## 主流程 `+ask`(最常用)

### Stage 1: 解析 + 轻澄清

agent 从用户提问里抽：
- **核心实体**(公司/人物/产品/行业)
- **时间窗口**(若用户没说，问 1 句确认)
- **角度**(投资/合规/竞品/舆情；若明显歧义，问 1 句)

只问 ≤1 个澄清问题。**不重写深研逻辑**——那是后端 rewrite_prompt 的活，留给 Stage 4。

### Stage 2: 匹配候选搭子(单阶段,看完整目录直接选)

agent **一次性拉取所有可见模板**(用户自建 + 系统公开搭子),按 `secondary_category` 在心里分组,然后**用自己的语义理解直接挑 top ≤2 个**——**不走后端关键词搜索**。后端 search 只匹配 title + primary/secondary category 字面,中文不分词,把「投资价值」/「业绩超预期」/「兆易创新」等都打回 0 命中(实测验证);agent LLM 的语义理解远强于这种字面匹配。

**实现:**

```python
from cue_api import search_templates
# 拉全集:keyword=" " + include_system=True,分页直到拿完(后端 page_size 上限 100)
pool, page = [], 1
while True:
    batch = search_templates(keyword=" ", include_system=True, page=page, page_size=100)
    if not batch: break
    pool.extend(batch)
    if len(batch) < 100: break
    page += 1
```

每个模板带 `title / primary_category / secondary_category / goal` 字段。agent 按 **`secondary_category`** 分组扫读(`深度核查` / `投资研究` / `信贷尽调` / `市值管理` / `财富投顾` / `私募尽调` / `融资融券` / `法律与行研` / `资本运作` / `行业研究` / `商机挖掘` / `保险营销` ...top 12 个 secondary cat 覆盖 ~80% 模板),拿 query 跟每个候选的 `goal` 做语义匹配,挑出最相关的 **≤2 个**候选。

**关键原则——主体 vs 意图分离:**

| 信息类型 | 例子 | 用法 |
|---|---|---|
| **主体 (entity)** | 兆易创新 / 万科 / 比亚迪 / 某监管文件名 | 留到 **Stage 4** 跑搭子时填 `task_input`,**绝不**进模板匹配的任何环节 |
| **意图 (intent)** | 投资价值 / 合规风险 / 财报点评 / 竞品对标 | agent 语义理解去匹模板的 goal/title/category |

**为什么必须分**:模板是**通用调研框架**,title/category/goal **永远不会**含具体主体名。把「兆易创新」当 query 跟模板匹配相当于让 agent 在通用框架里找具体主体——必然不知道选什么。agent 必须先在心里把 entity 剥出来给 task_input,只用 intent 做匹配。详见 Hard Rule 6。

**worked examples(实测验证 6 个真实 query,4 优于后端 keyword search,1 持平,1 诚实承认无匹配触发 weak-match):**

| 用户 query | 主体 (→ task_input) | 命中 secondary_cat → 候选 |
|---|---|---|
| 「兆易创新为什么值得投资」 | 兆易创新 | 投资研究 → `个股估值与股价分析` + `个股基本面与风险体检` |
| 「万科最近合规风险」 | 万科 | 法律与行研 + 深度核查 → `企业合规风险体检` + `监管处罚与问询全景` |
| 「调研一下宁德时代财报」 | 宁德时代 | 投资研究 + 财报点评 → `财报分析` + `财务质量与供应链核查` |
| 「这家公司毛利在变」 | (无显式主体) | 投资研究 + 财报点评 → `财务质量与供应链核查` + `个股基本面与风险体检` |
| 「比亚迪 vs 长城混动竞争」 | 比亚迪、长城 | 没完美匹配 → 触发 weak-match nudge |

**Context cost**: 今天 ~106 模板,~2.8K tokens,完全可控。

**未来扩展(标注 follow-up,今天不动)**: 库膨胀到 **200+ 模板** 后 context cost 跨过 ~6K tokens 阈值,需切换为**两阶段**:Stage A 只看 `secondary_category` + 模板数列表(~500 tokens)让 agent 选 1-3 个 cat,Stage B 只看那几个 cat 内的模板(~1-2K tokens)细选。今天单阶段最简单。

**仍要保留的低置信兜底**: agent 选完 top ≤2 后若自己判断匹配度都弱(query 跟选出来的搭子 angle 不一致),走下文 Stage 3 的 **weak-match nudge** 提示用户「要不做个新搭子?」。

### Stage 3: 呈现 + 用户确认

向用户展示，例如：

```
找到这些可能合适的搭子(关键词匹配，仅供参考)：
  1. <搭子A 标题> — <一句价值>
  2. <搭子B 标题> — <一句价值>
  0. 都不合适 → 走自由式深度调研(会先经过 /api/rewrite 做隐私脱敏 + 公开信源约束)
  n. 取消

确切 credits 跑完才知道(后端不提供 pre-run 估算，前几次主要用于校准；可在 cuecue.cn 工作台核对)。

**耗时**：单次深研**通常 3-15 分钟**，复杂主体更久；**服务端 60 分钟硬超时**。客户端/agent 等待应按此设置（不要按几十秒的常规 API 超时去掐），跑的过程中保持耐心、不要因为"久"就判定失败。
请输入: 
```

**弱匹配兜底:** 若 agent 判断列出的候选都跟用户问题**只在边角关键词上沾边**(标题/类目蹭到但 angle 对不上),在上面列表**后面**额外打一句:

> 匹配都不强——要不做个新搭子?

- 用户答"做" / "好" / "建" / "+author" 等正向回应 → **路由到 [`cue-buddy`](../cue-buddy) 的 `+author` 流**(注意:**对用户文案绝口不提 `+author` 这个 verb 名**,内部路由用;用户面只说"做个新搭子")。
- 用户答"不用" / "直跑" / 选 0 → 走 Stage 4b 自由式深研。

**这条提示只在弱匹配时给**——强/中匹配时正常展示 1/2/0/n,**不要打扰**用户。

### Stage 4a: 用户选 1/2 — 跑搭子

`chat_stream` 的真实签名是 `chat_stream(payload: dict, ...)`——**一个 payload dict,不是 kwargs**。构造方式:

```python
import uuid
from cue_api import chat_stream, replay            # 两者 SSE 格式一致,共用同一套 extract
from sse_report import extract_reporter_content, diagnose_empty_report

payload = {
    "messages": [{"role": "user", "content": <原问题或澄清后问题>}],
    "conversation_id": f"cue-research-{uuid.uuid4().hex[:12]}",  # 状态持久化需要 conv id
    "chat_id": uuid.uuid4().hex,
    "template_id": <选中的 template_id>,
    "need_analysis": False,   # 关键:别让后端中断流去澄清表单
    "need_confirm": False,
    "need_underlying": False,
    "need_recommend": False,
}
conv_id = payload["conversation_id"]
events = [(ev, d) for ev, d in chat_stream(payload, max_seconds=3600)]  # 对齐服务端 60min 硬超时
report = extract_reporter_content(events)
```

**标准路径:流跑完 → reporter 仍为空 → replay 兜底(不是异常,是常态)。** 深研单次 3-15 分钟,**live SSE 流经常在 reporter 段开始前就被客户端/网络掐断**(server 仍跑完写 DB)——所以 `extract_reporter_content(events)` 返回空字符串是**长跑的常见结果,不代表报告没生成、更不代表解析器坏了**。`chat_stream` 与 `replay` 的 SSE 解析逻辑完全一致(见 `cue_api.py`)、共用同一个 `extract_reporter_content`;replay 走的是后端 DB 里完整的 `workflow_events`,所以它几乎总能拿到 reporter 段。**因此 live 流空报告时必须照下面走 replay,把它当默认收尾而非错误处理:**

```python
if not report:                                       # 长跑下这是常态,不是 bug
    diag = diagnose_empty_report(events, elapsed, 3600.0)
    # diag["kind"] 是诊断结果字符串(不是函数!),取值之一:
    #   "stream_cut_before_reporter"  → live 流在 reporter 启动前断连 → replay 兜底
    #   "no_agent_events"             → 多半 auth/template_id 错,replay 也救不了
    #   "reporter_started_no_text"    → 服务端 reporter 真失败,去网页端查
    if diag["kind"] == "stream_cut_before_reporter":
        replay_events = [(ev, d) for ev, d in replay(conv_id, max_seconds=3600)]
        report = extract_reporter_content(replay_events)  # 同一个 extract,replay 几乎总能拿到
```

这套 L1 诊断分流 + L2 replay 兜底的**完整硬化版**(含三种 `kind` 的处理、`replay` 自身失败的提示)已在 `cue-buddy/scripts/test_template.py` 的 `main()` 里跑通 ≥9 个真实主体——**直接照抄它 `if not report:` 那一段即可,别自己重写**。注意 `stream_cut_before_reporter` 是 `diagnose_empty_report` 返回的 `kind` 字符串,**不是可 import 的函数**。

### Stage 4b: 用户选 0 — 自由式深度调研(经过 /api/rewrite)

1. 先调 `rewrite(input=<用户问题>)`(已自动 unwrap DataResponse 包装),拿到 dict,顶层就是 `thinking / user_confirmation / task_node / rewritten_mandate / safety_flag`。
2. 展示 `user_confirmation`(它会说明:要从什么视角调研、脱敏了哪些隐私)+ `safety_flag.pii_masked` 列表,问:
   > 这样调研行吗?
   > 1. 按此跑
   > 2. 我要改一下 query 重 rewrite
   > 3. 取消
3. 用户选 1,把 `rewritten_mandate` 作为 user message 发给 `chat_stream`,**payload 不带 `template_id`**(选 2 回到 Stage 1 拿新 query 重走;选 3 退出):

```python
payload = {
    "messages": [{"role": "user", "content": rewrite_result["rewritten_mandate"]}],
    "conversation_id": f"cue-research-{uuid.uuid4().hex[:12]}",
    "chat_id": uuid.uuid4().hex,
    # 不放 template_id — 自由式走 deepresearch_team
    "need_analysis": False,
    "need_confirm": False,
    "need_underlying": False,
    "need_recommend": False,
}
```

**为什么必须先 rewrite?** chat_stream 本身不调用 rewrite_prompt(只有 /api/rewrite 这个独立端点会)。跳过会丢掉隐私脱敏 + 公开信源约束 + 意图增强。

### Stage 5: 交付 + 满意度

展示报告(reporter content)。问:
> 这份报告满意吗?
> 1. 满意
> 2. 不满意

- 用户选 **1 (满意)** → 若刚才是 4b 自由式跑,转 Stage 6;若是 4a 搭子跑,直接结束。
- 用户选 **2 (不满意)** → 给后续选项,继续 1/2/3 风格:
  > 1. 换另一个候选搭子重跑(若 Stage 3 有多个候选还没用过)
  > 2. 补充澄清后重跑(回 Stage 1 改 query / 改主体 / 改时间窗)
  > 3. 改路径重跑(刚才是搭子 → 改自由式;刚才是自由式 → 改搭子,回 Stage 2 再匹配)

### Stage 6: 沉淀为搭子(可选 handoff 给 cue-buddy)

Stage 5 满意且是 4b 自由式跑时,问用户(**对外文案不出现 verb 名**):
> 这次调研有用,要不要存成一个新搭子?下次同类问题就有现成的可以用。
> 1. 存
> 2. 不用

用户选 **1** 后,agent **内部路由**(以下是给 agent 看的,不出现在跟用户的对话里):
- 把成功跑的 `conversation_id` + 原问题 + reporter 报告交给 cue-buddy 的 `+author` 流(后端按 `conversation_id` 取本次跑的历史用于生成模板)。
- 走 cue-buddy 的 `+validate` → 用户确认 → `+create` 落库。
- 这是**显式的、用户确认的**一步,不自动。**对用户文案只说"存""帮你存""做成搭子",不要说"+author"/"+validate"/"+create"**。

## 社区邀请（Cue 用户社群）

在**高意图时刻**邀请用户加入「Cue 用户社群」（答疑 + 最新搭子模板分享），按 [`../community-invite.md`](../community-invite.md) 的触发 + 冷却规则呈现群二维码——**克制、一行附加、不每次弹**：

- **① 首次使用**：首次 `+ask` 的呈现里低调一行（一次性）。
- **② 跑完一次调研后**：**报告 + 满意度/下一步问题都给完之后**附一行（**不得插在交付中间**）："好用?进群拿最新搭子模板"（14 天冷却）。
- **③ 卡住/报错**：匹配不到搭子 / 权限错 / 用户困惑时，**先帮用户处理 / 给下一步**，再把群作为**温和兜底**——不是报错就甩去群里（14 天冷却）。
- **④ 用户显式问**："怎么加群 / 社区 / 反馈 / 有没有新模板" → **展示二维码图片**（**不冷却**）。

**被动触发（①②③）只给一行文字 + 指向二维码 `../assets/community-group-qr.png`，不渲染大图；大图仅在 ④（用户主动要）时展示。** 加群入口只有二维码（已编码加群链接），**不发明文加群链接**。 冷却 `~/.cue/last-community-invite.json`（被动每会话最多一次、距上次 <14 天跳过；读写失败则本会话不再弹）。**外部群：飞书用户（含其它租户）可扫码加入；仅纯非飞书用户加不进**——完整规则与边界见 [`../community-invite.md`](../community-invite.md)。

## Hard rules(铁律)

1. **不自动选搭子**。永远让用户从 ≤2 候选 + "0 直跑" + "n 取消" 中选。
2. **每次真跑都显式确认 credits**。哪怕是用户选了"0 直跑"作为 fallback，也要再确认一次("自由式深研可能比有模板的更费 credits，确认继续？")。
3. **free-form 路径**(Stage 4b)**必须先调 /api/rewrite**。不要直接把用户原问题塞进 chat_stream。
4. **不在 agent 侧重写后端的 rewrite 逻辑**。要 rewrite 就调 /api/rewrite，要澄清 ≤1 句就好。
5. **不实现 `+delete`**(防误删；删搭子去网页工作台)。
6. **主体名(具体公司/人物/产品/事件名)只能进 `task_input`,绝不进模板匹配的任何环节**。模板是通用调研框架,title/category/goal 永远不含具体主体名——混进去会让 agent 把不该匹的硬匹上(或干脆无所适从)。匹配靠 agent 语义理解 query 的「意图」维度(投资/合规/财报/竞品...),主体名留给 Stage 4 跑搭子时填 task_input。这条规则与具体匹配机制无关,无论今天的全单选还是未来切两阶段都成立。详见 Stage 2。

## 安全规则

跟 cue-buddy 同源：API key 不出现在输出/日志/提交；用户粘了 key → 提醒去 cuecue.cn/api-key 立即轮换；本地材料不上传。

## 脚本到 verb 映射

| Verb | 走哪条路径 | 用到的脚本/函数 |
|---|---|---|
| `+ask` (主入口) | Stage 1-5 编排 | 复用：`cue_api.search_templates / rewrite / chat_stream / replay`；`sse_report.extract_reporter_content / diagnose_empty_report` |
| `+match` | 只跑 Stage 2-3 | `cue_api.search_templates` |
| `+rewrite` | 只跑 /api/rewrite | `cue_api.rewrite` |
| `+save` | Stage 6 handoff | 交给 cue-buddy 的 `generate_template` + `validate_template` + `cue_api.create_template` |
| `+upgrade` | 升级 skill 自身 | `python3 ../cue-buddy/scripts/update_skill.py --skill cue-research`(交互式) / 加 `--silent-check`(session 启动轻量版) |

本 skill 自己**没有专用脚本**——所有原语都在 `../cue-buddy/scripts/` 里(共享)。`cue-research/scripts/test_skill_regression.py` 只做结构/import 自检。

### 导入约定(运行时 bootstrap)

agent 在 cue-research 上下文里跑 Python 调上面这些函数时,`cue_api` 和 `sse_report` 不在默认 import 路径(它们在 sibling 的 `cue-buddy/scripts/`)。每段 Python 起手:

```python
import sys
from pathlib import Path
# cue-research/<...>  →  cue-skills/cue-buddy/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cue-buddy" / "scripts"))

from cue_api import search_templates, rewrite, chat_stream, replay
from sse_report import extract_reporter_content, diagnose_empty_report
```

如果是 agent 直接通过 Bash 跑 `python3 -c "..."`,改成绝对路径:`sys.path.insert(0, "<repo>/cue-buddy/scripts")`。规避点:不要在 cue-research/ 下复制粘贴 `cue_api.py`——会跟 cue-buddy 的版本漂移。

## 兼容性

| Platform | 状态 |
|---|---|
| Claude Code | 同 cue-buddy(SKILL.md 自动加载) |
| Gemini CLI / Codex CLI | 同 cue-buddy 加载约定 |
| Hermes / OpenClaw / Kimi | ✅ v0.2.0 cross-agent 已验证(真实任务 live API;同 cue-buddy 加载约定 + 共享脚本) |
