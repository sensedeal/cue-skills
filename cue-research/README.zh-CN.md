# cue-research

**[English](README.md) · [中文](README.zh-CN.md)**

**与 [`cue-buddy`](../cue-buddy) 是兄弟 skill。** cue-buddy 负责**做**（authoring）Cue 模板，cue-research 负责**用**——从你自己的 AI agent 里跑调研。

对话式循环：提问 → skill 从你的搭子库匹配 ≤2 个候选搭子（或走自由式深研）→ 你确认 → 后台跑 → 满意后可把自由式 run 沉淀成搭子，交给 cue-buddy。

一次深度调研**通常 3–15 分钟**（复杂主题更久），服务端**60 分钟硬超时**——客户端/agent 等待时间要按这个设，别把长任务当成失败。

## 需要与 cue-buddy 并列安装

cue-research 只带**一个薄运行时脚本**——`scripts/research_run.py`（发起 run → 取报告 → 存文件），它通过 `sys.path` bootstrap（见 `SKILL.md`）**组合**兄弟 [`../cue-buddy/scripts`](../cue-buddy/scripts) 里的 `cue_api` / `sse_report`，而不是复制一份。**两个 skill 必须作为兄弟目录装在同一父目录下**（比如都在 `~/.claude/skills/`）。单独装 cue-research 会在 import 时失败。（共享原语刻意不复制到这里，避免与 cue-buddy 版本漂移。）

`research_run.py` 在**后台**跑（SKILL.md 用 `run_in_background` 启动），把 **replay 当作报告获取的主路径**——长活 SSE 流常丢 reporter 段，所以它从 live 流提取、掉线回退到 replay（同一解析器，从后端 DB 读完整记录）。模式借鉴自 `cuecue-deep-research` 兄弟 skill（异步 + 文件输出）。

**仿写 / mimic**（仅自由式）：`--mimic-url <URL>` 或 `--mimic-file <path>` 让自由式报告模仿参考页面/样本文档的**写作风格与结构**（文件会上传换取 `file_hash`；后端把它解析成文本）。设计成一次性（`need_confirm=False`）以免打断后台执行；mimic 模仿风格，不复制结论。与搭子 `--template-id` 互斥。

状态：v0.3.6 — 见 `SKILL.md`。

> **v0.3.4 路径整合：** 运行时文件（报告 / 日志 / run）统一落在一个解析根 `<root>` = `python3 ../cue-buddy/scripts/cue_api.py root`（默认 `~/.cue`；home 不可写时回退 agent cwd 或临时目录——可移植，Windows 上不依赖 `/tmp/`）。报告从 `~/cue-reports/` 迁到 `<root>/reports/`——**旧报告在 `~/cue-reports/` 不自动搬**；新 run 走新默认路径。进度日志从 shell `> ./cue-run.log` 重定向改为 runner 自带的 `--log`（tee），启动与收尾的 Bash 调用共用同一条解析器选定的路径，不再硬编码。设 `CUE_HOME` 可整体迁移。

## License

[MIT](../LICENSE)
