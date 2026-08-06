---
name: cue-short-term-market
description: >
  用 Cue 跑「短线盘面」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Short-Term Trading" scenario.
  触发 Triggers: 短线盘面、行情与交易、财务与业绩 / short-term trading, intraday flow, dragon-tiger list, limit-up board
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "短线盘面"
  generated_from: /api/playbook
---

# Cue「短线盘面」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
短线盘面：行情与交易、财务与业绩。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 24h热点与催化剂追踪：短线题材捕捉手。实时追踪近24小时内全球重磅资讯，拆解其对权益市场的催化逻辑与受益板块，助你紧跟市场热钱流向。
  - 龙虎榜主力意图透视：看懂主力底牌。深度解析每日龙虎榜席位，区分“游资一日游”与“机构建仓”，识别席位协同与博弈特征，为投资者提供跟庄参考。
  - 深度盘前策略内参：交易员的盘前必读。扫描隔夜全球突发事件与技术突破，推导其对A股的逻辑映射与产业链传导，在开盘前锁定今日最具爆发力的主题。
  - 短线资金量价与技术面分析：围绕标的的历史行情、量价与强弱趋势，计算波动率、最大回撤与趋势结构，产出可复核的技术面分析底稿。
  - 盘中盘面透视：聚合早盘核心行情数据，穿透指数表象识别市场真实情绪与资金流向，定位逆势主线与风险雷区，输出包含明确操作建议的盘中观察评论
  - 热点板块资金逻辑分析：作为自营交易员，为您一键穿透[目标_时间_周期]内全A核心主线的资金流向与筹码结构，自动补全数据缺口并交叉验证，输出一份
  - 实时盯盘与交易日历：整合多标的实时行情、资金流、交易日历与全球财报宏观事件，产出一张可回查的盘中观察表。
  - 商品期货与黄金市场分析：拆解商品期货与黄金的行情趋势、主力资金博弈与库存交割变化，穿透会员多空持仓与仓单信号，产出可直接支撑交易与风险监控的市场

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "短线盘面"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
