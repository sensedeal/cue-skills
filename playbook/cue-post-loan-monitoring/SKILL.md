---
name: cue-post-loan-monitoring
description: >
  用 Cue 跑「贷后监测」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Post-Loan Monitoring" scenario.
  触发 Triggers: 贷后监测、企业尽调、信披与监管 / post-loan monitoring, borrower risk watch
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "贷后监测"
  generated_from: /api/playbook
---

# Cue「贷后监测」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
贷后监测：企业尽调、信披与监管、公司事件与资本运作。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 企业重大事件追踪：针对发酵中的热点事件（并购、涉诉、高管动荡等）构建演进时间轴，过滤噪音追踪实质进展，评估对信贷敞口的风险与业务切入点。
  - 存量客户风险预警：扫一遍授信客户名单，盯被执行、诉讼、评级下调与经营异动等风险信号，按紧迫度排序，产出可每日跟进的预警清单。
  - 股权质押风险核查：质押爆仓的雷，往往埋在到期日。核查控股股东的质押比例、集中度、距预警/平仓线的安全垫与到期分布，叠加股价和减持信号，看清
  - 贷后风险体检：对授信客户做贷后体检，从司法、被执行、股权质押与评级异动中摸排偿债风险，产出带证据链的体检底稿。
  - 司法执行与资产处置深挖：欠债的企业，名下还有什么能执行？穿透它的立案、裁判、终本、司法拍卖到产权交易全链路，把可处置资产线索摊在一张证据清单上，

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "贷后监测"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
