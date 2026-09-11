# Cue Playbook 场景 Skills

**[English](README.md) · [中文](README.zh-CN.md)**

这里每个子目录是一个 **playbook 场景的 agent skill**（`<slug>/SKILL.md`）。加载后，外部编码 agent（Claude Code / 第三方）可以用 Cue 跑该场景的深度研究、取回带来源的报告。

## 两种发布/使用方式

1. **整包**：把 `playbook/<scene>` 与自包含的 `cue-research` 装在同一父目录下，runner 已就位即可用。`cue-buddy` 可选——只有还要写/沉淀搭子时才需要。
2. **单场景（第三方 skill 市场）**：单独发某个 `<slug>/SKILL.md`。它**自带自举**——加载后若检测到本机没有 runner，会按正文指引 `git clone` 本开源仓到 `~/.cue/cue-skills`（整仓克隆是拿到自包含 `cue-research` runner 最省事的方式），GitHub 不通自动走 **Gitee 镜像** `https://gitee.com/sensedeal/cue-skills`，幂等（已存在则 `git pull`）。所以单文件也能独立跑通。

## 怎么用

1. 把某个 `<slug>/SKILL.md` 加载进你的 agent。
2. 按 skill 指令：**准备 runner**（整包已有则跳过；否则按"准备 Cue runner"段自举克隆）→ 运行时拉 live `https://cuecue.cn/api/playbook` 取该场景**当前**搭子 → 选一个 → 经 `research_run.py --template-id <id>` 跑 → replay 取报告。
3. 前置：`git` + `python3`；Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`）；跑深度研究**耗 credits**。新账号**赠送积分**（注册 500 + 每天 10），够先试用；每次深研前 skill 仍会确认再扣费。

## 设计要点

- **运行时查 live**：skill 不烤 `template_id`，运行时从 `/api/playbook` 取当前搭子 → 搭子动态增删改**自动反映**，无需重生成。
- **自动生成**：由 `scripts/gen_scene_skills.py` 从 `/api/playbook` + `GET /api/playbook/scenes/<scene>/skill` 端点生成。**场景集合变化**（新增/下线场景）时重跑生成器即可（`python3 scripts/gen_scene_skills.py --apply`）；搭子变动无需重跑。
- 单一生成源在 Cue 后端服务，本目录是其快照。
