---
name: cue-section-登记合规
description: >-
  当用户（或宿主 Agent）需要把 Cue「管理人尽调·登记与合规」节载荷写入自有底稿工作区时使用——首次创建最小底稿壳，或合并进已有壳。不用于整本尽调、制裁节或证据倾倒。
license: MIT
metadata:
  version: "0.1.0"
  requires:
    bins: ["python3"]
  envOptional: ["CUE_API_KEY"]
  dependsConceptually: ["cue-data-mcp"]
---

# Cue 节 · 管理人尽调 · 登记与合规

锁定闭环：**AMAC → 登记与合规节载荷 → 创建/合并最小管理人尽调底稿壳。**

## 触发词

- 管理人尽调登记合规
- 写入登记与合规节
- cue section 登记
- 首节创建底稿壳

## 宿主 Agent 步骤

1. 向用户确认主体关键词（缺则追问一次）。
2. 优先跑 `scripts/emit_and_merge.py --keyword '…'`；否则用 `cue-data-mcp` 调 AMAC 后按同样规则写文件。
3. 服从 `references/CONTRACT-CORE.md` 与 `references/TEMPLATE-登记合规.md`。
4. 只写本节（+ 首次最小壳）；不写整本。
5. 禁输出过界肯定句；`不得/禁止/不得据此` 窗内出现禁词字面可放行。
6. 回报：md 路径、创建或合并、≤3 判断、边界。

细节与英文版 `SKILL.md` 一致。
