---
name: cue-private-fund-dd
description: >
  用 Cue 跑「私募尽调」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Private-Fund Diligence" scenario.
  触发 Triggers: 私募尽调、企业尽调、基金与机构 / private fund due diligence, fund manager check
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "私募尽调"
  generated_from: /api/playbook
---

# Cue「私募尽调」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
私募尽调：企业尽调、基金与机构、信披与监管。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 私募管理人尽调底稿：约访谈之前，先把这家私募的底摸透。一次拉齐协会登记、管理规模、核心团队、产品运作、股权结构与处罚涉诉，产出带疑点清单、可
  - 私募产品状态监测：持仓的私募产品，悄悄清算了你都不知道。批量核验名单内每只产品的备案与运作状态，盯住提前清算、延期、已清算等异动并第一时间
  - 私募FOF准入风险筛查：一批候选管理人，先做一轮准入预筛。批量核验登记状态、规模一致性与信披诚信红线，分成可准入/需补材料/暂缓三档，标出每家红
  - 新登记私募发现与深挖：抢在同行之前发现值得跟的新私募。扫描中基协指定时段新登记的管理人，按地域和备案情况筛一遍，再对最有分量的几家做画像与高管
  - 私募新备案产品分析：最近谁在密集发产品？统计指定时段中基协新备案产品的数量与类型结构，揪出备案最活跃、短期集中发行的管理人，看清这段时间私募
  - 私募关联方与出资穿透：这家私募背后，到底还连着谁？用协会与工商信息核验出资人和关联方，逐个回查出资方是不是也是登记私募、有没有交叉持股或共用高

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "私募尽调"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
