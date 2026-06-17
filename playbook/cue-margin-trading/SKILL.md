---
name: cue-margin-trading
description: >
  用 Cue 跑「融资融券」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Margin Trading" scenario.
  触发 Triggers: 融资融券、行情与交易 / margin trading, margin balance, securities lending
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "融资融券"
  generated_from: /api/playbook
---

# Cue「融资融券」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
融资融券：行情与交易。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 两融竞对情报：横向比对各主要券商的两融政策（折算率、标的覆盖、保证金、集中度），识别竞对抢客与风险收缩信号、研判本方杠杆吸引力强弱，产
  - 两融竞对监测日报：每日差分各主要券商两融政策的单日变动（折算率调整、标的增减），第一时间锁定最显著的竞对异动并研判其引流或收缩意图，开盘前
  - ETF与科技两融对比：比对各券商在主流ETF与半导体等科技主题上的两融政策，看清谁对成长标的折算率更高、保证金更低，识别其争夺机构与量化客户的
  - 单券两融政策对比：针对单只证券横向比对各券商的折算率、标的状态与保证金比例，一眼看清这只票在哪家券商做两融更划算，支撑客户持仓沟通快速应答
  - 两融优质资产抢客雷达：在优质资产里揪出竞对比本方两融条件更优的证券（折算率更高、保证金更低或本方未支持），按抢客风险排序，输出可主动跟进的客户
  - 两融风险收缩预警：监控各券商对高波动、ST与大跌股的折算率下调及标的移出动作，横比本方与竞对的收缩节奏，预警行业两融风险偏好下行，助本方及

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "融资融券"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
