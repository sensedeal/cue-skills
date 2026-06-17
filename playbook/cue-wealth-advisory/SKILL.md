---
name: cue-wealth-advisory
description: >
  用 Cue 跑「财富投顾」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Wealth Advisory" scenario.
  触发 Triggers: 财富投顾、基金与机构、行情与交易 / wealth advisory, fund comparison, portfolio allocation
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "财富投顾"
  generated_from: /api/playbook
---

# Cue「财富投顾」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
财富投顾：基金与机构、行情与交易、财务与业绩。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 大类资产配置月报：宏观配置外脑。整合全球CPI、利率、国内宏观及资金流向，从宏观逻辑推导至股/债/商配置比例，一键生成月度资产配置建议书。
  - 盘后超级助理：10分钟自动生成深度市场复盘报告，穿透涨跌逻辑与资金流向；一键输出适配不同客群的专业点评与沟通话术，助你高效完成每日盘后
  - 投顾早盘简报：理财师的开工利器。自动汇总隔夜政策与外盘动态，生成即插即用的客户早报、热点问答话术与今日配置建议，助你高效开启一天的客户
  - 高净值财富内容工场：打造专家人设。基于宏观数据与专业叙事框架，为家办/高净值客户撰写具备“认知溢价”的深度文章、视频脚本与社交文案，征服高端
  - 财经早报：每日聚合全球宏观、A股异动、公司资本动作与隔夜外盘，穿透资金面与情绪面，提炼可直接转发客户的早报与点评。
  - 跨境税务合规展业指南：紧跟金税四期与境外收入严查风向，检索最新反避税法规与处罚判例，出具带法条依据的风险排查与合规重组建议。
  - 债基ETF与行业基金筛选：汇总权益基金换手与行业集中度、债基券种与风险指标、ETF申赎与行业重仓分布，构建可复核的基金候选池。

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "财富投顾"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
