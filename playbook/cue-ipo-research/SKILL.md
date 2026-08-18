---
name: cue-ipo-research
description: >
  用 Cue 跑「IPO研究」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "IPO Research" scenario.
  触发 Triggers: IPO研究、信披与监管、财务与业绩 / ipo pipeline, prospectus review, ipo inquiry, pre-ipo equity, fundraising plan
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "IPO研究"
  generated_from: /api/playbook
---

# Cue「IPO研究」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
IPO研究：信披与监管、财务与业绩、公司事件与资本运作。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - IPO项目进度雷达：按行业、板块与审核状态筛选 A 股在审 IPO 项目，逐项目还原从受理到发行的关键节点与最新动态，为投行项目储备、机构打
  - 问询焦点追踪：追踪 A 股 IPO 审核问询的焦点事项与监管关注方向：按主体还原其收到的审核问询内容（问询焦点/问询函/审核问询），按
  - 招股书穿透底稿：按章节穿透目标公司的招股说明书，形成可复核的尽调底稿：业务与技术、收入与财务、募投项目、风险因素四大板块逐项提取，并区分
  - 股权演变与激励核验：按主体还原上市前股权演变与员工持股安排：从设立至今的历次增资历史与股权转让历史（时点/金额/入股价格/交易方）、当前股权
  - 募投与可比公司分析：梳理拟上市主体的募集资金投向与同行业可比公司：募投项目构成与募集资金运用安排（项目名/总投资/拟用募集资金/投向）、可比

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "IPO研究"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
