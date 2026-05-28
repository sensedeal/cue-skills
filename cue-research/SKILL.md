---
name: cue-research
description: "Use when the user asks a research question they want Cue to answer. Triggers: 帮我查/调研/研究 + 主体或话题; ask Cue about X; 用 Cue 跑一下 Y. Matches ≤2 candidate buddies from the user's library (or falls back to free-form deep research with backend rewrite), confirms credits, runs, and offers to distill a successful free-form run into a saved buddy. Public-data scope only — refuse for private-data scenarios (real AML / medical / internal accounting)."
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

让你在自己的 AI agent 里**用自然语言把一个调研问题交给 Cue**：自动从你的搭子库里匹配 ≤2 个候选(或无合适搭子时改走"带后端 rewrite 的自由式深研")，确认 credits 后执行，跑完满意可以一键沉淀为搭子。本 skill 是 [`cue-buddy`](../buddy) 的兄弟 skill——cue-buddy 负责**做**搭子，cue-research 负责**用**搭子。

## 范围边界(避免起调用前踩坑)

Cue 工具面仅含**公开数据源**(工商/司法/监管/财报/资金流/招投标等)。需要私有数据的场景(真·反洗钱看银行流水、医疗诊断、企业内账)agent **拒绝执行**，提示用户改写成公开数据形态或去 cuecue.cn 网页端。

## 准备

跟 cue-buddy 共用一套 API key 配置(`CUE_API_KEY` env 或 `~/.cue/config.json`)。详见 [`../buddy/SKILL.md`](../buddy/SKILL.md) 的"准备"段。

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

### Stage 2: 匹配候选搭子

⚠️ **关键前置:先拆 query 成「主体」和「意图」两类信息**——只有意图词能匹配到搭子,主体名扔进 search 必然 0 命中。

| 类别 | 例子 | 用法 |
|---|---|---|
| **主体 (entity)** | 兆易创新 / 万科 / 比亚迪 / 某监管文件名 | 留到 **Stage 4** 跑搭子时填 `task_input`,**绝不**进 search keyword |
| **意图 (intent)** | 投资 / 估值 / 合规 / 财报 / 竞品 / 尽调 / 风险 | **只用这些**做 search keyword |

**为什么必须分**:模板是**通用调研框架**,标题/分类**永远不会**含具体主体名。实测验证:
- `search_templates("兆易创新")` → **0 命中**
- `search_templates("投资")` → 15 命中(含 `个股估值与股价分析` / `财报分析`)

**抽意图关键词的方法:**
- 看疑问/动词:「值得投资吗」 → `投资` / `估值` / `股价`
- 看角度:「合规风险」 → `合规` / `风险` / `尽调`
- 看场景/类型:「财报怎么样」 → `财报` / `业绩`;「竞品对比」 → `竞品` / `对标`

**worked examples:**

| 用户 query | 主体 (→ task_input) | 意图关键词 (→ search) |
|---|---|---|
| 「兆易创新为什么值得投资」 | 兆易创新 | `投资` / `估值` / `股价` |
| 「万科最近合规风险」 | 万科 | `合规` / `合规风险` |
| 「比亚迪 vs 长城混动竞争」 | 比亚迪、长城 | `竞品` / `对标` |
| 「调研一下宁德时代财报」 | 宁德时代 | `财报` / `业绩` |

**搜索时的注意事项:**
- 后端**不做中文分词**,**复合词易 miss**——`投资价值` 实测 0 命中,要拆短:`投资` + `估值` 分别试,合并去重。
- 用 **2-3 个意图词变体** search,union 后按相关性 rerank,**最多取 2 个**候选。
- 后端 search 只匹配 title + primary/secondary category(不查 goal/input),所以匹配是**关键词级、低置信** —— 不要 confidently 替用户选定;总是把"0 不用搭子直跑"作为合法选项。

### Stage 3: 呈现 + 用户确认

向用户展示，例如：

```
找到这些可能合适的搭子(关键词匹配，仅供参考)：
  1. <搭子A 标题> — <一句价值>
  2. <搭子B 标题> — <一句价值>
  0. 都不合适 → 走自由式深度调研(会先经过 /api/rewrite 做隐私脱敏 + 公开信源约束)
  n. 取消

确切 credits 跑完才知道(后端不提供 pre-run 估算，前几次主要用于校准；可在 cuecue.cn 工作台核对)。
请输入: 
```

**弱匹配兜底:** 若 agent 判断列出的候选都跟用户问题**只在边角关键词上沾边**(标题/类目蹭到但 angle 对不上),在上面列表**后面**额外打一句:

> 匹配都不强——要不做个新搭子?

- 用户答"做" / "好" / "建" / "+author" 等正向回应 → **路由到 [`cue-buddy`](../buddy) 的 `+author` 流**(注意:**对用户文案绝口不提 `+author` 这个 verb 名**,内部路由用;用户面只说"做个新搭子")。
- 用户答"不用" / "直跑" / 选 0 → 走 Stage 4b 自由式深研。

**这条提示只在弱匹配时给**——强/中匹配时正常展示 1/2/0/n,**不要打扰**用户。

### Stage 4a: 用户选 1/2 — 跑搭子

`chat_stream` 的真实签名是 `chat_stream(payload: dict, ...)`——**一个 payload dict,不是 kwargs**。构造方式:

```python
import uuid
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
for event, data in chat_stream(payload, max_seconds=900):
    ...  # 累 reporter content; 见 sse_report.extract_reporter_content
```

复用 `sse_report.extract_reporter_content` 累报告;空报告时用 `diagnose_empty_report` 分类原因,`stream_cut_before_reporter` 走 `replay(conversation_id)` 兜底。这一套硬化逻辑在 `buddy/scripts/test_template.py` 已经验证过 4 个真实主体,直接照抄它的事件循环即可。

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
- 把成功跑的 `conversation_id` + 原问题 + reporter 报告交给 cue-buddy 的 `+author` 流(`generate_template` 用 `template_history_by_conversation_id(conversation_id)` 真的能拿到本次跑的历史,详见 cubemanus template.py:226-259)。
- 走 cue-buddy 的 `+validate` → 用户确认 → `+create` 落库。
- 这是**显式的、用户确认的**一步,不自动。**对用户文案只说"存""帮你存""做成搭子",不要说"+author"/"+validate"/"+create"**。

## Hard rules(铁律)

1. **不自动选搭子**。永远让用户从 ≤2 候选 + "0 直跑" + "n 取消" 中选。
2. **每次真跑都显式确认 credits**。哪怕是用户选了"0 直跑"作为 fallback，也要再确认一次("自由式深研可能比有模板的更费 credits，确认继续？")。
3. **free-form 路径**(Stage 4b)**必须先调 /api/rewrite**。不要直接把用户原问题塞进 chat_stream。
4. **不在 agent 侧重写后端的 rewrite 逻辑**。要 rewrite 就调 /api/rewrite，要澄清 ≤1 句就好。
5. **不实现 `+delete`**(防误删；删搭子去网页工作台)。
6. **Stage 2 关键词必须 strip 主体名**。模板是通用调研框架,标题/分类**永远不含**具体主体名;用「兆易创新」/「万科」/「比亚迪」等实体名当 search keyword **必然 0 命中**。主体名只放进 Stage 4 的 `task_input`,**不进 search 关键词**。实测见 Stage 2 段。

## 安全规则

跟 cue-buddy 同源：API key 不出现在输出/日志/提交；用户粘了 key → 提醒去 cuecue.cn/api-key 立即轮换；本地材料不上传。

## 脚本到 verb 映射

| Verb | 走哪条路径 | 用到的脚本/函数 |
|---|---|---|
| `+ask` (主入口) | Stage 1-5 编排 | 复用：`cue_api.search_templates / rewrite / chat_stream / replay`；`sse_report.extract_reporter_content / diagnose_empty_report` |
| `+match` | 只跑 Stage 2-3 | `cue_api.search_templates` |
| `+rewrite` | 只跑 /api/rewrite | `cue_api.rewrite` |
| `+save` | Stage 6 handoff | 交给 cue-buddy 的 `generate_template` + `validate_template` + `cue_api.create_template` |
| `+upgrade` | 升级 skill 自身 | `python3 ../buddy/scripts/update_skill.py --skill cue-research`(交互式) / 加 `--silent-check`(session 启动轻量版) |

本 skill 自己**没有专用脚本**——所有原语都在 `../buddy/scripts/` 里(共享)。`cue-research/scripts/test_skill_regression.py` 只做结构/import 自检。

### 导入约定(运行时 bootstrap)

agent 在 cue-research 上下文里跑 Python 调上面这些函数时,`cue_api` 和 `sse_report` 不在默认 import 路径(它们在 sibling 的 `buddy/scripts/`)。每段 Python 起手:

```python
import sys
from pathlib import Path
# cue-research/<...>  →  cue-skills/buddy/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "buddy" / "scripts"))

from cue_api import search_templates, rewrite, chat_stream, replay
from sse_report import extract_reporter_content, diagnose_empty_report
```

如果是 agent 直接通过 Bash 跑 `python3 -c "..."`,改成绝对路径:`sys.path.insert(0, "<repo>/buddy/scripts")`。规避点:不要在 cue-research/ 下复制粘贴 `cue_api.py`——会跟 cue-buddy 的版本漂移。

## 兼容性

| Platform | 状态 |
|---|---|
| Claude Code | 同 cue-buddy(SKILL.md 自动加载) |
| Codex CLI / Gemini CLI | 同 cue-buddy 加载约定，未独立验证 |
