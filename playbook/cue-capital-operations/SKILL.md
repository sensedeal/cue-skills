---
name: cue-capital-operations
description: >
  用 Cue 跑「资本运作」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Capital Operations" scenario.
  触发 Triggers: 资本运作、公司事件与资本运作、信披与监管 / capital operations, M&A, private placement
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "资本运作"
  generated_from: /api/playbook
---

# Cue「资本运作」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
资本运作：公司事件与资本运作、信披与监管、财务与业绩。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 资本运作解读：全量回溯公司资本运作、深挖战略意图、评估市场影响，帮管理层客观评价过往动作的市值贡献，并为未来回购、分红、并购决策提供参
  - 股份回购查询与复盘：用历史溯源、条款深挖、同业对标与市场复盘，研判回购对护盘、价值发现与股本优化的成效，为市值管理决策提供数据支撑。
  - 股权激励企业挖掘：截胡雷达。筛出估值低位且现金充裕、有动力推股权激励的未公告标的，抢在同行前面锁定B端大单。
  - 股权激励查询：查询上市公司历史股权激励计划，分析方案设计与效果，拉取同行竞品方案对比，用真实数据告诉你什么才有竞争力。
  - 调研纪要解读：解码上市公司资本运作交流会纪要的核心信息，多维验证管理层指引可信度、穿透历史言行一致性，挖掘未被市场定价的风险与机会。
  - 事件风险与资本运作时间线：穿透公司的并购重组、股东增减持、机构调研、监管处罚与重大诉讼，把结构化事件与披露原文放在同一条时间线上复核。

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "资本运作"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
