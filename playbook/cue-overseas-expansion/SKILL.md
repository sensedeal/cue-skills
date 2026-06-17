---
name: cue-overseas-expansion
description: >
  用 Cue 跑「出海企业线索」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Overseas Expansion Leads" scenario.
  触发 Triggers: 出海企业线索、企业尽调、信披与监管 / overseas expansion, sanctions screening, export control
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "出海企业线索"
  generated_from: /api/playbook
---

# Cue「出海企业线索」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
出海企业线索：企业尽调、信披与监管、全网检索。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 跨境制裁与海外执法筛查：跨境合作前，先看清对方的海外合规记录。对主体及关联名单做制裁名单、海外监管披露、经纪合规与执法记录筛查，产出一份可逐条回
  - 跨境法规调研：定向检索目标司法辖区法律法规原文与核心条款，提炼立法背景与适用边界，每个结论附原始出处可逐条回查。
  - 出海企业资质尽调底稿：ODI备案核实、海外实体关系梳理、海关AEO与海外涉诉筛查，产出可回查的出海资质底稿。
  - 出海企业跨境业务线索：锁定指定区域内有ODI备案、实际出海动作的跨境企业，按开户/结算/发债/并购等需求精准匹配商机，输出可派单的线索清单。
  - 目的地国营商准入扫描：扫一遍目的地国的外商投资准入——负面清单、敏感行业审批、税务/劳动/数据合规要点，产出可回查的落地底稿。

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "出海企业线索"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
