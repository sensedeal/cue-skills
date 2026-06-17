---
name: cue-deep-verification
description: >
  用 Cue 跑「深度核查」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Deep Verification" scenario.
  触发 Triggers: 深度核查、企业尽调、信披与监管 / deep verification, fact check, cross-source verification
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "深度核查"
  generated_from: /api/playbook
---

# Cue「深度核查」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
深度核查：企业尽调、信披与监管。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 事实核查：穿透待核查资讯的表层表述，通过独立信源交叉验证与底层数据复核，精准识别时间错位、数据偏差及误导性信息，产出包含原文对照与
  - 地址核查：交叉比对工商注册与高精度地图POI数据，一键识别主体错配、行政区划错误与虚拟地址，输出含修正建议的核查底稿。
  - 工商与知识产权核查：摸清一家企业的家底与无形资产。补全工商年报、股权变更、土地与对外投资，再叠加专利、商标、著作权清单，产出一份主体档案 +
  - 财报极速排雷：用财务诊断框架快速扫描企业利润含金量、产业链话语权、典型财务雷区,叠加司法监管与同业对照,产出可回查的风险信号清单与证据
  - 财报前瞻指引兑现核查：管理层的业绩指引，到底能不能信？把公司的业绩预告与发布时的市场一致预期、以及后续实际兑现三方对账，看它是连续兑现还是惯于
  - 交易对手资质与信用核查：投标准入前逐条比对供应商声称的资质、业绩与承诺，标清属实/不符/查无此项，亮红旗。
  - 研报观点可信度核查：把研报的盈利预测、评级目标价与增长逻辑，与一致预期、历史兑现、同业分歧核对，给出可信度分层、预期差与乐观偏差提示。
  - 上市公司承诺兑现核查：把公司及股东的公开承诺（回购、增减持、业绩对赌、激励解锁）与实际兑现交叉核对，标注已兑现/进行中/未达标并量化完成率，揪

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "深度核查"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
