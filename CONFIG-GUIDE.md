# AzureProxy + AzureBranches 配置手册（简单版）

> 目标：从零搭起「代理 + 双后端」小服，能进、能切、计分板正常、`/team` 可用。
> 配套版本：AzureBranches **EXP7Plus**（v26.1.2-EXP7Plus）+ AzureProxy **v26.1.2-AP-0001**。
> 详细原理见 [TECHNICAL.md](TECHNICAL.md)；本文只讲怎么配。

## 0. 这套东西是什么（30 秒版）

```
玩家 ──► AzureProxy（代理，25571）──► 后端 exp7（25570，正式世界）
                                  └──► 后端 arena（25572，测试世界）
```

- **AzureBranches**＝服务器本体（Folia 下游）。它让单个后端拥有了：`b_linear_v4` 存储引擎、命令 OCC（EXP 链）、计分板/团队修复等。
- **AzureProxy**＝入口代理（Velocity 下游）。它做三件事：**一个地址进多个后端**、**玩家随时切服**（`/server`）、**后端掉线自动换后备**。
- 玩家只连代理，永远不直接连后端。

## 1. 准备

| 需要 | 说明 |
|---|---|
| JDK 25 | 运行与构建都需要 |
| jar 文件 | 方式一：去 GitHub Releases 下载；方式二：本地构建（见 §2） |
| 目录规划 | 每个后端一个文件夹（如 `server-exp7/`、`server-arena/`），代理一个文件夹（如 `proxy/`）；**互相独立**，别混放 |

## 2. 拿 jar

**方式一：下载（推荐）**
- 后端：[AzureBranches Releases](https://github.com/XCxyTianQ/AzureBranches/releases) → `v26.1.2-EXP7Plus` → `azurebranches-server-26.1.2-AB-0002-EXP7Plus.jar`
- 代理：[AzureProxy Releases](https://github.com/XCxyTianQ/AzureProxy/releases) → `v26.1.2-AP-0001` → `azureproxy-proxy-26.1.2-AP-0001.jar`

**方式二：本地构建**
```bash
# 后端（AzureBranches 目录）
./gradlew.bat :azurebranches-server:buildFolia :azurebranches-server:mergeJar
# 产物：folia-server/build/libs/azurebranches-server-26.1.2-AB-0002-EXP7Plus.jar

# 代理（AzureProxy 目录）
./gradlew buildAzureProxyJar
# 产物：build/libs/azureproxy-proxy-4.1.0-SNAPSHOT-all.jar
```

## 3. 搭后端（每个服一次）

以 `server-exp7/` 为例（arena 同法，换个端口即可）。

**3.1 基础文件**
```bash
mkdir server-exp7 && cd server-exp7
# 放入 azurebranches-server-26.1.2-AB-0002-EXP7Plus.jar
echo "eula=true" > eula.txt
```

**3.2 `server.properties`（改 / 加这几行即可）**
```properties
server-port=25570
online-mode=false
level-name=world-exp7
motd=My AzureBranches Server
enable-rcon=true          # 可选：远程控制台
rcon.port=25576
rcon.password=改一个强密码
```

**3.3 `config/paper-global.yml` → 打开代理转发（关键！）**
```yaml
velocity:
  enabled: true
  online-mode: false
  secret: 一个和代理完全一样的随机串
```
> ⚠️ `secret` 必须与代理的 `forwarding.secret` 文件内容**逐字符一致**，否则玩家身份/UUID 会错乱或登录被拒。建议用 24+ 位随机串。

**3.4 `azurebranches_global_config.toml`（服务器根目录）→ 开启 EXP 档与存储引擎（可选）**
```toml
[command_blocks]
mode = "EXP"          # SAFE（上游默认）| ACCESS | EXP；EXP = 命令链 OCC 全套

[storage]
region_format = "b_linear_v4"   # "mca"（默认，原版）| "b_linear_v4"

[storage.linear]
compression_level = 1            # 1..22，压缩级别，默认 1
```
> 建议：新世界直接用 `b_linear_v4`（写入更快 + 四层校验）；老世界（已有 MCA 数据）先备份再考虑。

**3.5 启动**
```bash
java -Xmx2G -jar azurebranches-server-26.1.2-AB-0002-EXP7Plus.jar nogui
```
看到 `Done (…)!` 即成功。三个维度 + entities（`r.*.mca`）会落在该世界区域里，`v4` 主文件与 `.swp` 交换文件同目录。

> ⚠️ **开了 `velocity.enabled: true` 的后端，只能经代理进入**——玩家直连会被拒（转发校验）。这是正常现象。

## 4. 搭代理

在 `proxy/` 目录：放入代理 jar + `forwarding.secret` 文件：

```
proxy/
├── azureproxy-proxy-26.1.2-AP-0001.jar
├── forwarding.secret        # 内容 = 后端 paper-global.yml 的 velocity.secret（一模一样）
└── velocity.toml            # 见下
```

**`velocity.toml`（最小可跑样例）**
```toml
bind = "0.0.0.0:25571"          # 玩家连的地址；本机测试可写 127.0.0.1
online-mode = false
player-info-forwarding-mode = "MODERN"
forwarding-secret-file = "forwarding.secret"

[servers]
exp7 = "127.0.0.1:25570"
arena = "127.0.0.1:25572"

try = ["exp7", "arena"]          # 进服与掉线时按顺序尝试

[azureproxy]
mode = "EXP"                     # SAFE | ACCESS | EXP，见 §5
```

**启动**
```bash
java -jar azureproxy-proxy-26.1.2-AP-0001.jar
```
看到 `Booting up AzureProxy …` 与 `[AzureProxy] azureproxy.mode=EXP applied (log-command-executions=true, announce-proxy-commands=true)` 即成功。

## 5. 代理档位怎么选

| mode | 一句话 | 适用 |
|---|---|---|
| `SAFE` | 和原版 Velocity 一模一样，零改动 | 只想当纯代理 |
| `ACCESS` | 多记录命令执行日志 | 排错/观察 |
| `EXP` | 观察 + 强制代理命令树（`/server` 可 tab 补全）+ 未配置时强制 MODERN 转发 | **常规用途（推荐）** |

> **为什么日常就用 EXP**：T1 修复后，`EXP` 档保证客户端命令列表里 `/server` 是白色、可补全；改成 SAFE 只影响这些预设，不影响进服。

## 6. 后端档位与代理档位对照

| 后端 `command_blocks.mode` | 代理 `[azureproxy] mode` | 效果 |
|---|---|---|
| `SAFE` | `SAFE` | 全上游默认，最保守 |
| `EXP` | `EXP` │ `ACCESS` | 命令链 OCC + 代理命令面（**推荐组合**） |

两个开关独立：代理档管「网络/命令面」，后端档管「命令链 OCC」。

## 7. 日常使用

| 想干什么 | 怎么做 |
|---|---|
| 进服 | 客户端连 `你的IP:25571`（或服务器列表地址），自动进 `try` 的第一个 |
| 切服 | 游戏内 `/server exp7` 或 `/server arena`；输入 `/server ` 有自动补全 |
| 世界隔离 | 每个后端是独立世界：`/say`/`/tell` 只在本服广播 |
| 管理员 | 每后端各自 `ops.json`（`op 玩家名` 分别执行），互不影响 |
| 后端宕机 | 代理自动切换 `try` 里下一个可用后端，通常同一秒完成 |
| 计分板 | EXP7Plus 已修复：重进后 sidebar 正常（会重发 SetObjective/Display/Score） |
| 团队 | EXP7Plus 已恢复：`/team add|join|modify color|list …` 全部可用 |

## 8. 常见问题排查

| 现象 | 原因与解法 |
|---|---|
| 重进后计分板消失（服务端数据还在） | 后端不是 EXP7Plus 版本 → 换 `azurebranches-server-26.1.2-AB-0002-EXP7Plus.jar` |
| `/team` 报 Unknown command | 同上（旧版本 Folia 禁用了 team，EXP7Plus 已恢复） |
| `/server` 红色未知命令 / 无 tab 补全 | 代理 `[azureproxy] mode` 不是 `EXP`（或高级配置里 `announce-proxy-commands=false`）→ 用 EXP 档 |
| 能直连后端、经代理进不去/被拒 | 后端开了 `velocity.enabled: true` → 必须走代理；或 secret 不一致 |
| UUID 每次不同 / 身份错乱 | `velocity.secret`（后端）≠ `forwarding.secret`（代理）→ 改成一致 |
| `Booting up AzureProxy` 未见 EXP 行 | 检查 `velocity.toml` 的 `[azureproxy] mode` 段拼写/位置（应在文件末尾独立一节） |
| 切服卡在加载 | 目标后端没启动或端口错 → 先确认后端 `Done` 且端口匹配 `[servers]` |

## 9. 版本对应关系

| 组件 | 版本 | jar |
|---|---|---|
| 后端 | v26.1.2-EXP7Plus（当前） | `azurebranches-server-26.1.2-AB-0002-EXP7Plus.jar` |
| 代理 | v26.1.2-AP-0001 | `azureproxy-proxy-26.1.2-AP-0001.jar` |

> 往后端掉期都可以分开选版（例如后端 EXP7、代理 AP-0001），但 **EXP7Plus 的两个修复（计分板登录同步、/team）只在后端侧**，与代理版本无关。
