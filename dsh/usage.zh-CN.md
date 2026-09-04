# 使用 Cue 的 DSH 组合包 —— 指南与 FAQ

**[English](usage.md)** · [中文](usage.zh-CN.md)

两个可发布的 bundle,把 Cue Omni Reader 接入 DeepSeek Harness profile,并让你给它加固:

| 包 | 作用 | 安装 |
|---|---|---|
| [`@cueai/dsh-omni-reader`](../cue-omni-reader) | 接入审校版 Omni Reader MCP server → 工具 `mcp__omni__*` | 必装 |
| [`@cueai/dsh-omni-reader-guard`](../cue-omni-reader-guard) | 可选 `tools/pre-execute` 护栏(SSRF / 白名单 / 同意) | 可选,装在其上 |
| [`@cueai/dsh-cue-data-mcp`](../cue-data-mcp) | 暴露 Cue 的公开数据 MCP 服务 → 工具 `mcp__cue_<domain>__*`(15 域 / ~104 工具) | 可选 |

## 安装

```sh
dsh plugin --profile web add @cueai/dsh-omni-reader
dsh plugin --profile web add @cueai/dsh-omni-reader-guard   # 可选
dsh plugin --profile web add @cueai/dsh-cue-data-mcp        # 可选(数据工具)
dsh --profile web --dump-config            # 确认 mcp-omni + guard 行
```

重启后模型可见 `mcp__omni__parse` / `…get_parse_status` / `…cancel_parse` / `…read_result` / `…read_outline` / `…discard_result` / `…save_result`。

## 配置 wiring 包

全部由环境变量驱动(patch 里无密钥/无路径)。在 `$DSH_HOME/.env` 里设置,或在启动 dsh 前 export:

```sh
CUE_API_KEY=sk-...                    # 必填 —— 来自 https://cuecue.cn/hub/api-key
OMNI_ALLOWED_ROOTS=/home/you/workspace  # 可选;默认 dsh cwd
```

Bridge **固定为 `@cueai/omni-reader-mcp@1.7.1`**(审校版;永不用隐式 `latest`)。要求 Node ≥ 20.12。

## 配置 guard 包(默认 fail-closed)

```yaml
config:
  blockPrivate: true          # 拒绝私网/回环/链路本地/云元数据主机(SSRF)
  allowList: []               # 免同意主机;裸域名含其子域
  allowedRoots: []            # 可选:设置显式绝对目录以允许本地文件
  policyForUnknown: deny      # deny | ask | allow(不在 allowList 的外部主机)
  consentReason: '解析外部 URL 前请确认(将消耗 Cue 积分)'
```

| 结果 | 何时 |
|---|---|
| **deny** | 私网/保留主机;`allowedRoots` 为空时的本地路径;`policyForUnknown=deny` 的外部主机 |
| **allow** | 白名单主机;`allowedRoots` 内的本地路径 |
| **ask** | `policyForUnknown=ask` 的外部主机(需 DSH approval 服务返回 `allowed-once`,否则退化为 deny) |

`allowedRoots` **默认为空 → 本地文件被拒**。要解析本地文件必须显式配置:

```yaml
config:
  allowedRoots: [!!js process.cwd()]   # 或一个显式绝对目录
```

## FAQ

**问:为什么我的本地文件被拒?**
护栏默认 `allowedRoots` 为 `[]`(fail-closed)。按上面的方式加一个显式绝对目录即允许本地解析。

**问:为什么这个公开 URL 被拒?** 不在 `allowList` 且 `policyForUnknown=deny`。要么把主机/域名加进 `allowList`,要么设 `policyForUnknown: ask` 做一次性确认。

**问:为什么私网 / `localhost` URL 被拒?** 那是 SSRF 门禁(`blockPrivate: true`)。因为 Omni 可拉取任意 URL,护栏阻止它访问内部/元数据主机。

**问:如何放行整个域名?** `allowList: ['example.com']` 放行该域名及其子域;`allowList: ['*.example.com']` 仅放行子域。

**问:`ask` 到底需要什么?** 只有当 DSH approval 通道返回 `allowed-once` 时才会弹出确认;没有则被拒(fail-closed)。无人值守 agent 建议 `allowList` + `deny`。

**问:我需要装 guard 吗?** 不必——wiring 包可单独工作。guard 是给"agent 能自选解析目标、想限制 SSRF 与费用"的部署用的。

**问:怎么验证?** `dsh --profile web --dump-config`,再试一次小解析;并跑仓库检查:`node --test dsh/cue-omni-reader-guard/test/policy.test.js`、`node dsh/cue-omni-reader-guard/test/smoke.mjs`、`python3 scripts/verify_dsh_bundles.py`。

## 许可 / scope

两个包都是 `@cueai/*`(公开 scope)且 MIT;自带测试与 CI(`verify-dsh-bundles`)保证改动可被门禁拦截。
