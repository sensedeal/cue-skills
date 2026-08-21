---
name: cue-cross-border-legal
description: >
  用 Cue 跑「涉外法律」场景的深度研究：多源公开数据交叉、结论带来源。
  Run Cue deep research for the "Cross-border Legal" scenario.
  触发 Triggers: 涉外法律、信披与监管、企业尽调 / sanctions screening, export control, cross-border legal
license: MIT
metadata:
  source: cuecue.cn/playbook
  scene: "涉外法律"
  generated_from: /api/playbook
---

# Cue「涉外法律」研究 skill

加载本 skill 后，你可以用 Cue 跑这个场景的深度研究（多源公开数据交叉、结论带来源链接）。

## 何时用
涉外法律：信披与监管、企业尽调、全网检索。

## 当前可用搭子（仅供理解；运行时以 live 为准）
  - 贸易救济与出口合规：跟踪目标行业在全球主要市场的反倾销/反补贴/保障措施等贸易救济调查动态，映射涉案企业清单与税率变化，识别出口合规风险(实
  - 跨境法规调研：定向检索目标司法辖区法律法规原文与核心条款，提炼立法背景与适用边界，每个结论附原始出处可逐条回查。
  - 境外诉讼案例库：中国企业出海，最怕在别人地盘上吃官司。围绕一个主题检索主要法域的公开判例与监管公告，归纳诉因、判决倾向与对中国主体的合规
  - 关联方制裁暴露核查：从股权穿透扩出关联主体集，逐个核查OFAC/欧盟/新加坡制裁名单，产出主体-关系-命中/未命中-来源的暴露底稿。
  - 药企跨境合规全球监管动向与营销：以正式法律文本、官方名单、实施规则和监管文件为主，拆解涉外监管对合同、采购、贷款、拨款和供应链的适用边界与法定步骤。用户
  - 中外法律对比：围绕一个法律议题横跨多法域取法条原文与学术文献,做比较法分析——各法域规则异同、立法背景与学界观点,产出带原文出处与引文
  - 制裁与出口管制暴露筛查：核查一个主体及其关联方是否被美国（OFAC、BIS 实体清单、涉军企业等）及欧盟、新加坡的制裁与出口管制清单列名、分别属
  - 美国管制风险全景核查：核查一个中国企业的美国管制风险暴露（CFIUS/ICTS/UFLPA/1260H/BIS/SEC/FDA/FINRA），

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
1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "涉外法律"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。 读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

## 前置
- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 50 + 每天 10），可先免费试。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。
