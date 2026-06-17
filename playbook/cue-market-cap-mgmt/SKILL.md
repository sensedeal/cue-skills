---
name: cue-market-cap-mgmt
description: >
  用 Cue 跑「市值管理」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Market-Cap Management" scenario.
  触发 Triggers: 市值管理、公司事件与资本运作、行情与交易 / market cap management, buyback, shareholding changes
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "市值管理"
  generated_from: /api/playbook
---

# Cue「市值管理」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
市值管理：公司事件与资本运作、行情与交易、信披与监管。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 并购标的挖掘：全网扫描并购猎物。结合产业政策与技术成熟度，快速筛选符合战略协同的优质标的，提供初步尽调风险提示与交易结构建议。
  - 市值管理策略方案：针对估值偏差、业绩波动等痛点，从价值创造—传播—实现三维构建全流程市值管理方案，产出可落地的决策依据。
  - 潜在上市企业挖掘：发现未来的独角兽。通过专利布局、融资轮次等多维信号，量化预测企业的上市概率，为投行Pre-IPO布局提供高确定性项目源。
  - 激励方案设计：设计符合最新企业战略的股权激励方案，提升员工积极性与企业价值，适用于上市公司激励计划制定。
  - 市值监测日报：每日动态跟踪上市公司及竞争对手股价波动、核心财务指标，检测相关舆情资讯，并从价值创造、价值经营、价值实现角度提供系统化的
  - 上市公司速览：5分钟看懂一家公司。结构化呈现治理结构、财务健康、产业链地位及潜在投行业务机会，提升投前/业务调研效率，为业务开发人员提
  - 市值健康度诊断：诊断上市公司的市值定位与管理体系短板，产出含市值定位、系统诊断、核心问题与优化方向的市值管理诊断报告。
  - 非上市企业估值监控：不依赖商业计划书，用招聘、专利、流量等另类数据穿透经营黑盒，锚定非上市企业的公允价值与融资断档风险。

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "市值管理"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
