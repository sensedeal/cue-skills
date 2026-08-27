# @cueai/dsh-omni-reader-guard

**中文** · [English](README.md)

一个可选的 **DeepSeek Harness** bundle,用于加固 Omni Reader 的 `parse` 工具。它注册一个 `tools/pre-execute` 监听器,门控 `mcp__omni__parse`,使模型无法静默解析任意 URL。请在 [`@cueai/dsh-omni-reader`](../cue-omni-reader) wiring bundle **之后/旁边**安装它。

## 它做什么

在 `mcp__omni__parse` 调用派发前,护栏会对 `source` 分类:

| source | 结果 |
|---|---|
| **私网 / 回环 / 链路本地 / 云元数据主机**(`10/8`、`172.16/12`、`192.168/16`、`127/8`、`169.254.169.254`、`100.64/10`、`fe80::`、`fc00::`、`::1`、`localhost`、`*.local`、`metadata…`) | **deny**(SSRF 护栏) |
| **白名单主机**(`allowList`) | **allow** |
| 其它外部主机 | `policyForUnknown` —— `deny`(默认)、`ask` 或 `allow` |
| **显式配置的 `allowedRoots` 内的本地路径** | **allow** |
| **`allowedRoots` 之外的本地路径,或未配置 `allowedRoots`** | **deny**(fail-closed) |

其它工具原样放行(护栏只针对 `mcp__omni__parse`)。它同时门控 `source` 参数与 `url` 别名(Bridge 1.5+ 二者只取其一)。

## 安装

```sh
dsh plugin --profile web add @cueai/dsh-omni-reader-guard
# 或一次性:
dsh web --patch ./dsh/cue-omni-reader-guard/cordis.patch.yml
```

## 配置

通过 bundle 的 `cordis.patch.yml` `config`(无密钥、无硬编码部署路径):

| 字段 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `blockPrivate` | boolean | `true` | 拒绝私网/保留主机(SSRF 门禁) |
| `allowList` | string[] | `[]` | 免同意的宿主/域名(裸域名也放行其子域;`*.x` 仅子域) |
| `allowedRoots` | string[] | `[]`(本地文件**被拒**) | 本地 `source` 必须落在其中的绝对目录。**须显式设置**才允许本地解析;空 = fail-closed |
| `policyForUnknown` | `'deny'`\|`'ask'`\|`'allow'` | `'deny'` | 不在 `allowList` 的外部主机的结果 |
| `consentReason` | string | … | `policyForUnknown: ask` 时的提示文案 |

示例:放行一个可信 API 主机,其余需同意。

```yaml
config:
  blockPrivate: true
  allowList: ['api.example.com']
  policyForUnknown: ask
```

## 验证

```sh
node --test dsh/cue-omni-reader-guard/test/policy.test.js
python3 scripts/verify_dsh_bundles.py
```

## 说明

- `ask` 需要 DSH 的 approval 服务返回 `allowed-once`;没有则退化为 deny(fail-closed)——见 `tools/pre-execute` 瀑布契约。
- 这是护栏,不是沙箱:它过滤主机与本地根,**不**改写参数。把 `allowedRoots` 收到最小,无人值守 agent 建议用 `deny` + 显式 `allowList`。
- 核心策略(`policy.js`)是纯 Node(`node:url`/`node:net`),所以安全逻辑无需活 DSH 即可测试。

## 许可

MIT — 见 [LICENSE](../../LICENSE)。
