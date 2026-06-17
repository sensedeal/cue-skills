---
name: cue-industry-research
description: >
  用 Cue 跑「行业研究」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Industry Research" scenario.
  触发 Triggers: 行业研究、产业链与研报、财务与业绩 / industry research, value chain, sector landscape
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "行业研究"
  generated_from: /api/playbook
---

# Cue「行业研究」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
行业研究：产业链与研报、财务与业绩、宏观与日历。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 新兴产业研究：面对陌生赛道一键梳理行业天花板、竞争格局与核心商业模式，映射IPO/并购中常见的合规风险与法律争议点。
  - 传统行业研究：支持搜行业或搜公司，拆解赛道天花板、竞争格局与商业模式，穿透龙头供应链，并内置合规排雷核查 IPO/融资法律风险，产出兼
  - 热门赛道/基金深度投研：路演逐字稿生成器。从宏观政策、指数编制到成分股质量，全维度深度扫描特定赛道，为你回答客户“这个赛道到底有没有价值”提供硬
  - 行业景气与竞争格局研判：穿透目标行业的景气周期、竞争格局与产业链地位，识别集中度、龙头壁垒与供需/政策拐点，研判当前所处周期位置与投资机会窗口，
  - 行业产业政策与影响：追踪发改委、工信部等主管部门的政策出台与修订，拆解对准入、竞争格局和资本流向的传导，产出政策影响研判底稿。

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "行业研究"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
