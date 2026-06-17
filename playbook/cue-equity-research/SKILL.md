---
name: cue-equity-research
description: >
  用 Cue 跑「投资研究」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Equity Research" scenario.
  触发 Triggers: 投资研究、财务与业绩、公司事件与资本运作 / equity research, stock fundamentals, company valuation
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "投资研究"
  generated_from: /api/playbook
---

# Cue「投资研究」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
投资研究：财务与业绩、公司事件与资本运作、信披与监管。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 24h热点与催化剂追踪：短线题材捕捉手。实时追踪近24小时内全球重磅资讯，拆解其对权益市场的催化逻辑与受益板块，助你紧跟市场热钱流向。
  - 个股估值与股价分析：融合短线资金流向与中长线估值模型，全周期分析——短期看情绪博弈与支撑压力，中长期看业绩兑现与安全边际。
  - 产业链潜力股挖掘：寻找下一个领涨龙头。梳理产业链传导路径，基于基本面与弹性逻辑，挖掘具备业绩爆发潜力的“隐形冠军”。
  - 龙虎榜主力意图透视：看懂主力底牌。深度解析每日龙虎榜席位，区分“游资一日游”与“机构建仓”，识别席位协同与博弈特征，为投资者提供跟庄参考。
  - 深度盘前策略内参：交易员的盘前必读。扫描隔夜全球突发事件与技术突破，推导其对A股的逻辑映射与产业链传导，在开盘前锁定今日最具爆发力的主题。
  - 财报分析：分层获取上市公司全量财务科目与指标，做审计前置检查、三表交叉分析与造假风险排查，产出含估值击球区判断的深度财报研报。
  - 个股基本面与风险体检：穿透公司的业务、三年三表、杜邦拆解、估值与行业横比，把财务事实、经营质量与风险信号放进同一份可复核的基本面体检底稿。
  - 资金流向全景追踪：覆盖权益市场各类型机构资金的流入流出，穿透板块、风格与主题维度，产出可追溯的周度资金面底稿，支撑投资决策。

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "投资研究"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
