---
name: cue-person-check
description: >
  用 Cue 跑「人物核查」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Person Background Check" scenario.
  触发 Triggers: 人物核查、企业尽调、全网检索 / person background check, executive history, related entities
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "人物核查"
  generated_from: /api/playbook
---

# Cue「人物核查」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
人物核查：企业尽调、全网检索、信披与监管。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 个人背调底稿：穿透人物的全生命周期工商与司法轨迹，剥离当前在册与历史风险、映射其商业控制版图，产出可用于 IPO 或重大交易的背调底稿
  - 基金经理言行核查：他嘴上说的，和实际操作一致吗？把基金经理公开宣称的选股逻辑、换手与风控，和真实持仓、集中度、回撤归因逐项对账，揪出言行偏
  - 关键人物批量核查：给一批人名，批量核查每人的失信、限高、被执行、行政处罚、股权冻结等公开风险，逐人定级、按风险排序，产出合作或准入前可用的
  - 企业管理层风险体检：批量穿透企业董监高与实控人的对外任职、失信、限高与被执行，逐人定级排序，产出尽调前可用的管理层风险清单。
  - 实控人关联穿透：从一家企业穿透到实控人与最终受益人，画出其关联企业网络、对外担保圈、资金占用与隐性代持线索，识别关联交易与利益输送风险，

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "人物核查"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
