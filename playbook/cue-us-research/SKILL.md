---
name: cue-us-research
description: >
  用 Cue 跑「美国投研一站式」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "US Equity Research" scenario.
  触发 Triggers: 美国投研一站式、财务与业绩、行情与交易 / US equity research, US macro, US company analysis
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "美国投研一站式"
  generated_from: /api/playbook
---

# Cue「美国投研一站式」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
美国投研一站式：财务与业绩、行情与交易、产业链与研报、信披与监管。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 美股个股360体检：多源穿透一家美股公司的披露、多年财务、风险因素与MD&A正文、内部人交易及合规与政府订单敞口,补全公开盲区,产出可上初审
  - 美国通胀劳动力追踪：追踪美国通胀(CPI/PPI)、工资、就业与职位空缺(JOLTS)及消费增长的最新读数,自动算同比环比、标出拐点与边际变
  - 美国财政流动性周报：追踪美国财政部 TGA 余额、每日财政现金流(DTS)、发债节奏与债务变化,研判财政对银行体系流动性是抽水还是投放,一份
  - COT持仓结构扫描：针对指定期货品种,拆解大投机、商业对冲与小散的持仓结构,计算净持仓、周环比与历史百分位,标出极端拥挤与背离,产出跨品种可
  - 原油供需与持仓周报：交叉美国原油库存、产量与进出口(EIA)和投机与商业持仓(CFTC COT),把供需基本面与持仓情绪拼成一条,一份周报看
  - 美国AI生医多资产简报：横跨宏观、头部公司、政府投入、监管风险与多资产持仓,把美国AI与生物医药的产业叙事落到股/债/商品/情绪四类资产上,产出
  - SEC申报监控：盯住一家或一组美股公司的最新申报,推送重大8-K事件、内部人Form4买卖与新IPO的S-1,第一时间抓住可能驱动股价的
  - 美国产业赛道扫描：扫描一个美国产业赛道的地理footprint、联邦订单流向与研发资助风向,把企业分布、政府投入与创新热度拼成一张市场结构

## 准备 Cue runner（首次用时，幂等）
本 skill 不自带脚本，靠 Cue 开源 runner 跑研究。先确认 runner 是否就绪：
- 若你已安装 `cue-skills`（或本 skill 来自整包发布）→ 直接用其中的 `cue-research/scripts/research_run.py`，**跳过本节**。
- 否则克隆开源仓（含 cue-research + cue-buddy 全套依赖），**有则更新、无则克隆**（GitHub 不通走镜像）：
  ```bash
  if [ -d ~/.cue/cue-skills/.git ]; then
    git -C ~/.cue/cue-skills pull --ff-only
  else
    git clone https://github.com/sensedeal/cue-skills ~/.cue/cue-skills \
      || git clone https://gitee.com/sensedeal/cue-skills ~/.cue/cue-skills
  fi
  ```
  之后 runner = `~/.cue/cue-skills/cue-research/scripts/research_run.py`。需 `git` + `python3`（runner 仅用标准库）。

## 怎么跑（搭子是动态的，运行时查 live）
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "美国投研一站式"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
