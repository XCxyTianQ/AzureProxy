# AzureProxy 技术文档（TECH-SPEC v1）

> 状态：随实现更新（1.0 对应 `velocityRef = 4772ca3` 基线 + T1 修复后状态）
> 定位：AzureBranches 的**代理侧配套**。上游 [Velocity](https://github.com/PaperMC/Velocity) 的
> GPLv3 下游；本仓库只持有构建驱动 + 补丁 + 文档，上游源码按固定 ref 克隆后打补丁构建。
> README（使用向）见 [README.md](README.md)；本文件（原理向）说明：为什么、在哪改、靠什么验证。

## 1. 项目概览

| 项 | 值 |
|---|---|
| 基线 | `dev/4.0.0` @ `4772ca3022c49bfab37c703f72cbca7654fb5848`（Velocity 4.1.0-SNAPSHOT） |
| 构建 | Gradle **9.4.1**（复用 AzureBranches 的 wrapper/distribution，不下载上游默认 9.6.1），JDK 25 |
| 产物 | `build/libs/azureproxy-proxy-4.1.0-SNAPSHOT-all.jar`（shadowJar，`velocity-` 前缀重命名为 `azureproxy-`） |
| 补丁 | `azurepatches-src`（整文件覆盖层）+ `azurepatches-new`（新增文件） |
| 许可 | GPLv3 + NOTICE（与 Velocity / AzureBranches 一致） |
| 配套 | AzureBranches EXP7（b_linear_v4 存储引擎，`command_blocks.mode=EXP`） |

职责边界：**AzureProxy 不改后端**。所有修改都在代理侧；后端侧只保留 AzureBranches 的
`paper-global.yml` 中 `velocity.enabled: true`（现代转发开关）与 ops 授权。

```
repo (AzureProxy)
 ├── build.gradle.kts         驱动：cloneVelocity → applyAzurePatches → buildVelocity → buildAzureProxyJar
 ├── azurepatches-src/…       覆盖层（必须有对应上游文件，fail-fast）
 ├── azurepatches-new/…       新增类（com.azureproxy.*）
 ├── gen-velocity-config-overlay.py   由上游源文件一键再生成覆盖层（锚点插入）
 ├── mcclient.py / mcping.py  E2E 工具（合成 protocol-775 客户端 / status 探测）
 └── build/velocity-src/      上游克隆（gitignored，按 ref 固定，HEAD 漂移即失败）
```

## 2. 构建驱动（build.gradle.kts）

核心工具函数：

| 函数 | 作用 |
|---|---|
| `sh(dir, cmd…)` | 外部命令执行（stdout 直通） |
| `gw(dir)` | Windows → `gradlew.bat`，否则 `./gradlew` |
| `transformSource(file, label, old, to)` | **fail-fast 唯一锚点替换**：锚点缺失或匹配 >1 次直接抛错（上游漂移立即曝露） |
| `ensureWrapperPinned()` | 把 `gradle-wrapper.properties` 的 distributionUrl 钉到 9.4.1（仅首次写入） |

任务链（依赖：buildAzureProxyJar → buildVelocity → applyAzurePatches → cloneVelocity）：

### 2.1 `cloneVelocity` —— 固定 ref 克隆（幂等）
- 克隆不存在：`git init` → 加 remote → `fetch --depth 1 <ref>` → `checkout --detach FETCH_HEAD`。
- 克隆已存在：`git rev-parse HEAD` 与 `velocityRef` 严格比对，**不等即抛错**（防漂移，提示按 re-baseline 流程处理）。

### 2.2 `applyAzurePatches` —— 补丁应用
- `azurepatches-src`：先**全量校验每个文件在上游存在**（fail-fast，README.md 约定文件除外），再整体覆盖；
- `azurepatches-new`：按相对路径拷贝（新增文件）；
- 两层的 `README.md` 均为目录约定说明，**跳过**（否则会覆盖上游同名文件，见 commit `956708a`）。

### 2.3 `buildVelocity` —— 品牌 + 编译
1. `git checkout -- proxy/build.gradle.kts` 先还原构建文件（`transformSource` 非幂等，克隆会累积上次品牌修改——幂等性由还原保证）；
2. `transformSource` × 2：`Implementation-Title` `Velocity→AzureProxy`、`Implementation-Vendor` `Velocity Contributors→AzureProxy Contributors`（`VelocityServer.getVersion()` 读 Manifest，启动横幅 `Booting up AzureProxy <ver>...`）；
3. `ensureWrapperPinned()`；
4. `:velocity-proxy:compileJava --no-configuration-cache`（含 spotless/checkstyle 等上游校验链）。

### 2.4 `buildAzureProxyJar` —— 打包
- `:velocity-proxy:shadowJar` → 从 `proxy/build/libs` 挑最大非 `-sources/-javadoc` jar → 重命名 `velocity-` → `azureproxy-` → 拷到仓库 `build/libs/`（如 `azureproxy-proxy-4.1.0-SNAPSHOT-all.jar`）。

## 3. 补丁系统

### 3.1 `azurepatches-src`（整文件覆盖）
适用：需修改上游文件多处位置（当前仅 `VelocityConfiguration.java`）。
- 覆盖目标必须存在（`applyAzurePatches` 校验）——上游布局变化时构建报「无对应上游文件」，不会静默丢包；
- 保持上游代码风格（4 空格缩进、spotless 通过，构建即可验证）。

### 3.2 `azurepatches-new`（新增文件）
适用：上游不存在的新类（当前仅 `com.azureproxy.config.AzureProxyMode`）。
- 包前缀固定 `com.azureproxy.*`（对应 AzureBranches 的 `com.azurebranches.*`）。

### 3.3 覆盖层生成器 `gen-velocity-config-overlay.py`
`VelocityConfiguration.java` 覆盖层不是手敲的：脚本从 `build/velocity-src` 的 `HEAD:…` 读上游原文，
对唯一锚点 `PacketLimiterConfig.fromConfig(...)` 做插入，写回 `azurepatches-src`。re-baseline 后
重跑一次即可再生成（锚点重复/缺失会 assert 失败即失败）。

## 4. azureproxy.mode 预设体系

### 4.1 动机
与 AzureBranches 的 `command_blocks.mode`（SAFE/ACCESS/EXP 三档）同构：一个开关，把代理侧
网络/命令面一次性重调到目标后端族，而不是让用户手工改多个 Velocity 选项。

### 4.2 配置与读取
`velocity.toml`：

```toml
[azureproxy]
mode = "SAFE"        # SAFE（默认）| ACCESS | EXP
```

`AzureProxyMode.applyToConfig(root, advanced)` 从 raw nightconfig 读取 `azureproxy.mode`
（未配置 → SAFE）。解析失败（未知字符串）→ 打印警告并保持 SAFE（fail-soft）。

### 4.3 挂载点（为什么在这里）
见 `VelocityConfiguration.read()`（覆盖层）：

```java
packetLimiterConfig = PacketLimiterConfig.fromConfig(...);
// ← AzureProxyMode.applyToConfig(config, advancedConfig) 插在这里
…（forwarding-secret 非空校验）
return new VelocityConfiguration(bind, …, new Advanced(advancedConfig), …);
```

选择依据：
- **在 nightconfig 绑定之前**改写原始配置：预设经上游正常构造器/迁移/校验链生效，不绕过任何语义；
- **在 forwarding-secret 校验之前**：EXP 强制 `MODERN` 时，上游对 forwarding secret 的既有校验
  照常执行（不会出现"强制了 MODERN 却没人管 secret"）——如果插在正式绑定之后，就只能绕过校验或
  自行重写一段等效逻辑。

### 4.4 档位行为

| 档位 | advanced 变更 | 其他 | 启动日志 |
|---|---|---|---|
| SAFE（默认） | 无 | — | `azureproxy.mode=SAFE (upstream defaults)` |
| ACCESS | `log-command-executions = true` | — | `azureproxy.mode=ACCESS applied (…)` |
| EXP | `log-command-executions = true` **且强制 `announce-proxy-commands = true`** | `player-info-forwarding-mode` 未显式配置时设为 `MODERN`（显式配置则尊重用户） | `azureproxy.mode=EXP applied (log-command-executions=true, announce-proxy-commands=true)` |

> **为什么 EXP 强制 `announce-proxy-commands=true`（T1）**：该选项决定 Velocity 是否向后端
> AvailableCommands 合并代理命令树。若为 `false`，客户端命令树中没有 `/server` 等代理命令——
> 表现为 `/server` 红色未知命令 + 零 tab 补全。上游默认 `true`；早前的 EXP preset 误设 `false`
> 导致此问题（见 §7.1）。EXP 因此显式 `set(true)`，**绝不依赖上游默认而把自己"永续修正"**。

### 4.5 已知语义
- `log-command-executions`：ACCESS/EXP 共用的运维观察项；
- `player-info-forwarding-mode = MODERN`：EXP7 后端现代转发配套（后端 `velocity.enabled=true` +
  `forwarding.secret` 一致），uuid 跨后端一致由 velocity 现代转发保证（实测见 §7.4）。

## 5. 协议适配（26.1 / protocol 775）

### 5.1 版本矩阵
`api/.../network/ProtocolVersion.java`（上游）：

```
MINECRAFT_26_1(775, "26.1", "26.1.1", "26.1.2")
MINECRAFT_26_2(776, "26.2")
```

### 5.2 StateRegistry 26_1 关键 id（已验证，velocity 上游表即正确）
`proxy/.../protocol/StateRegistry.java` 的 26_1 条目**无需修补**（26_1 对齐结论：
velocity 4.0.0-dev 的表与真实 26.1.2 客户端一致）。关键实测 id：

| 方向 | 包 | id | 备注 |
|---|---|---|---|
| CB | BundleDelimiter | **0x00** | 1.19.4+ 常驻 0x00 —— 索引抽取时易漏，见 §5.3 |
| CB | KeepAlive | **0x2C** | 26_1 条目显式存在 |
| CB | JoinGame（LOGIN） | **0x31** | 26_1 条目显式存在 |
| CB | SystemChat | **0x79** | 26_1 条目显式存在 |
| CB | Respawn / Transfer / StoreCookie | 0x52 / 0x81 / 0x78 | 26_1 条目显式存在 |
| CB | AvailableCommands | **0x10** | 26_1 无独立条目，按 1.21.5 的 0x10 继承（客户端实测 cmdpacket pid=0x10） |
| SB | ServerboundPlayerLoaded | **0x2C** | 26_1 条目显式存在（进世界必需，见 §6.2） |
| SB | ClientTickEnd / chat_command_signed | 0x0D / 0x08 | StateRegistry 未注册（Velocity 透传）；mcclient 直发、后端接受 |

### 5.3 经验教训：索引抽取陷阱（+1 假象）
26.1 客户端方向的 `BundleDelimiter` 占据 `0x00`，靠"按顺序数索引"从数据表抽取 id 会被整体
**+1 偏移骗过**（早期曾据此"修正"velocity 表 27 处，全部是误报，已 revert）。正确做法：
以**真实客户端实测**为准（§6.2 mcclient 全流程 + 真实 XY_TianQ 客户端会话），表与实测互证。

### 5.4 遗留
- **26.2 (776)**：协议表刷新与探测（mcclient 776 回归）**未验证**（当前暂缓）。

## 6. 测试与验证工具链

### 6.1 `mcping.py` —— status 探测
MC 1.7+ 握手 + status 请求 + JSON 解析（版本/协议号/MOTD 人数）。默认 `proto=775`。

### 6.2 `mcclient.py` —— 合成 775 客户端（E2E 主干）
`mcclient.py <host> <port> <name> [cmd]`：离线登录 → 配置阶段 → PLAY → 发签名命令 →
断言 SystemChat 回显；全程抓 `raw-dump.bin` + pid 直方图，退出码 0/1 表示断言结果。

**阶段流**（26.1/1.21.9+ 关键点）：

| 阶段 | 客户端动作 |
|---|---|
| LOGIN | handshake(proto=775) → LoginStart(name+uuid) → SetCompression(0x03) → LoginSuccess(0x02) → LoginAcknowledged(0x03) |
| CONFIG | 收 `FinishedUpdate(0x03)` → ack 进入 PLAY；`CookieRequest` 忽略；收到特定 pid 后发 `ClientInformation(0x00)`；收到 KnownPacks(0x0E) 后回 `SelectKnownPacks(0x07)`（空选择） |
| PLAY | 收到 JoinGame 标记后：发 `ServerboundPlayerLoaded(0x2C)`（必须，否则后端认为玩家未加载完）；每 0.2s 发 `ServerboundClientTickEnd(0x0D)`（**1.21.9/26.1 起必需**，缺了后端会踢/判定非活跃）；发 `chat_command_signed(0x08)`（name + ts + salt + 签名占位）；扫信道收 SystemChat 回显（0x78/0x79 候选，实际 0x79） |

> 注：`chat_command_signed` 的签名体为占位（`msg_signature`/`signed_headers` 全零），后端解码器
> 接受即可（26.1 非强制验证签名）；`summon UUID:[I;…]` 等命令在 26.1.2 有随机 UUID 缺陷，
> 冒烟脚本改用 `@e` 选择器断言（§6.3）。

### 6.3 `exp7proxy-smoke.py`（AzureBranches 侧 RCON 冒烟）
经 RCON（exp7 25576 / arena 25578）发 EXP 链命令并断言：`@e` 选择器 + 空列表 ghost 断言
（避开 26.1.2 summon UUID 缺陷）；[PASS]/[FAIL] 逐项输出；对代理侧验证「代理命令/后端命令
经代理信道的结果」。

### 6.4 测试布局（本机）

| 组件 | 端口 | 目录 |
|---|---|---|
| AzureProxy（EXP 模式） | 25571（bind 127.0.0.1） | `proxyrun-test/velocity.toml`（servers: exp7=25570 / arena=25572；try=[exp7,arena]；`[azureproxy] mode="EXP"`） |
| exp7 后端（b_linear_v4） | 25570 / RCON 25576 | `F:\AzureCore\AzureBranches\exp7-test\`（`exp7-rcon.py`、`exp7-v4-run*.log`） |
| arena 后端（seed 987654321） | 25572 / RCON 25578 | `F:\AzureCore\AzureBranches\exp7-test2\`（`arena-rcon.py`、`arena-run*.log`） |

两侧 `paper-global.yml`：`velocity.enabled=true`；各后端独立 `ops.json`（Velocity 语义）。

## 7. 验证矩阵（实测结论）

### 7.1 T1 —— 命令树注入（已修复 ✅）
- **现象**：代理模式下 `/server` 红色未知命令、零 tab 补全。
- **根因**：EXP preset 残留下游默认改写 `advanced.set("announce-proxy-commands", false)`；
  Velocity 依此不把代理命令树并入发给客户端的 AvailableCommands。
- **修复**：`AzureProxyMode.applyToConfig` EXP 分支强制 `announce-proxy-commands = true`；
  启动日志同步打出该值（`…announce-proxy-commands=true`）。
- **证据（实测）**：
  - 代理侧合并后 AvailableCommands children 26 → 28（注入 `server` 子树 + `velocity:callback`）；
  - 真实客户端命令包 `pid=0x10 len=718`，内含 `velocity:callback`、`server` (+`action`/`target`) 节点；
  - 真实客户端（XY_TianQ）：`/ser` tab 补全 `server`，命令白色，`/server exp7|arena` 执行正常（用户确认）。

### 7.2 服务器切换（Velocity 核心 ✅）

| 验证项 | 结果 |
|---|---|
| `/server arena` 切换 / `/server exp7` 切回 | ✅ 世界差异可辨（seed/地形/出生点） |
| 世界隔离 | ✅ `/say` 只广播本世界 |
| 转发身份一致性 | ✅ 跨后端同 UUID `2b47bbd5-9532-3390-b1b6-8392740fa849`（MODERN 转发） |
| Op 独立性 | ✅ 每后端各自 `ops.json` |

### 7.3 Fallback（后端宕机瞬时切换 ✅）
kill arena → 代理日志同一秒 `arena has disconnected` / `exp7 has connected`；exp7 后端
`joined the game`；用户确认**无世界加载等待**（瞬时）。

### 7.4 E2E / 协议链路（✅）
mcclient 全流程：握手 → 压缩 → 登录 → 配置 → PLAY（PlayerLoaded + TickEnd）→
`chat_command_signed` → SystemChat 回显 → VERDICT 全真；真实客户端信道 `/say` 确认。

## 8. re-baseline（提升上游 ref）流程

1. `git ls-remote https://github.com/PaperMC/Velocity.git refs/heads/dev/4.0.0` 取新 ref；
2. 更新 `build.gradle.kts` 的 `velocityRef`；
3. 删除 `build/velocity-src/` → `./gradlew cloneVelocity`；
4. `./gradlew applyAzurePatches`：fail-fast 报出失效 overlay 锚点，逐项修复
   （`VelocityConfiguration.java` 覆盖层改动前先重跑 `gen-velocity-config-overlay.py` 再手工合入）；
5. 协议相关：以 `mcclient` 实测为准（§5.3 教训），不盲信索引抽取；
6. `./gradlew buildAzureProxyJar` 全绿 → 启动验证（EXP 日志行 + `/server` 补全）→ 提交。

## 9. 已知限制与遗留

| 项 | 状态 |
|---|---|
| 26.2 (776) 协议表刷新 + mcclient 776 回归 | 暂缓（未验证） |
| `summon UUID:[I;…]` 26.1.2 随机 UUID 缺陷（后端侧） | 冒烟脚本以 `@e` + 空表断言规避 |
| mcclient 压缩阈值 varint / 早期解帧边界 | 已修；仅测试工具，不影响运行时代码 |
| fallback 测试期间 arena 后端需手动重启 | 测试脚本化未完成 |

## 附录：仓库结构与关键文件索引

```
AzureProxy/
├── build.gradle.kts                         # 构建驱动（§2）
├── azurepatches-src/                        # 覆盖层（§3.1）
│   └── proxy/src/main/java/com/velocitypowered/proxy/config/VelocityConfiguration.java
├── azurepatches-new/                        # 新增（§3.2）
│   └── proxy/src/main/java/com/azureproxy/config/AzureProxyMode.java
├── gen-velocity-config-overlay.py           # 覆盖层生成器（§3.3）
├── mcclient.py / mcping.py                  # E2E 工具（§6.1/6.2）
├── build/velocity-src/                      # 上游克隆（gitignored，pin ref）
├── proxyrun-test/                           # 本机测试配置（velocity.toml 等，gitignored）
├── LICENSE / NOTICE.md                      # GPLv3 + 致谢
└── README.md                                # 使用向文档
```
