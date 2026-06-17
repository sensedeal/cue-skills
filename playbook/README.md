# Cue Playbook 场景 Skills

这里每个子目录是一个 **playbook 场景的 agent skill**（`<slug>/SKILL.md`）。加载后，外部编码 agent（Claude Code / 第三方）可以用 Cue 跑该场景的深度研究、取回带来源的报告。

## 怎么用
1. 把某个 `<slug>/SKILL.md` 加载进你的 agent。
2. 按 skill 指令：运行时拉 live `https://cuecue.cn/api/playbook` 取该场景**当前**搭子 → 选一个 → 经 `cue-research/scripts/research_run.py --template-id <id>` 跑 → replay 取报告。
3. 前置：Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`）；跑深度研究**耗 credits**。新账号送免费积分(注册 50 + 每天 10),可先免费试。

## 设计要点
- **运行时查 live**：skill 不烤 `template_id`，运行时从 `/api/playbook` 取当前搭子 → 搭子动态增删改**自动反映**，无需重生成。
- **自动生成**：由 `scripts/gen_scene_skills.py` 从 `/api/playbook` + `GET /api/playbook/scenes/<scene>/skill` 端点生成。**场景集合变化**（新增/下线场景）时重跑生成器即可（`python3 scripts/gen_scene_skills.py --apply`）；搭子变动无需重跑。
- 单一生成源在后端（cubemanus），本目录是其快照。

设计 spec：cubemanus `docs/playbook_scene_skills_design_2026_06_16.md`。
