---
name: cue-insurance-marketing
description: >
  用 Cue 跑「保险营销」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Insurance Marketing" scenario.
  触发 Triggers: 保险营销、企业尽调、全网检索 / insurance product analysis, coverage comparison
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "保险营销"
  generated_from: /api/playbook
---

# Cue「保险营销」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
保险营销：企业尽调、全网检索、财务与业绩。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 保险产品对比指南：横向比对目标产品与竞品在保障、收益、服务与适配场景上的差异，产出可直接用于客户沟通的选型对比建议。
  - 保险营销线索日报：获客素材库。每日扫描医疗/社会热点，自动映射关联保险需求，生成直击痛点的朋友圈文案与一句话营销线索，用新闻事实低成本挖掘
  - 保险产品适当性与需求匹配核查：核验产品的保障、费率、退保与利益不确定性，并对照客户公开可述需求做适当性匹配，产出可如实说明的需求匹配底稿（不含销售话术
  - 保险产品条款核查：逐条核验保险产品的保障责任、责任免除、等待期、费率与退保损失，并与同类产品客观对比，产出一份可向客户如实说明的条款理解底
  - 保险合规红线速查：梳理监管处罚与消费者风险提示，提炼该主题下的销售合规红线与禁用表达，帮一线对齐「可如实说明」与「不可承诺」的边界。

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "保险营销"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
