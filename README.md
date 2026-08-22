# AzureProxy

> 与 [AzureBranches](https://github.com/XCxyTianQ/AzureBranches) 并列的 [PaperMC Velocity](https://github.com/PaperMC/Velocity) 下游实验项目（同属 AzureCore），配套 EXP7（b_linear_v4 存储引擎）的代理侧同步适配。仓库：[XCxyTianQ/AzureProxy](https://github.com/XCxyTianQ/AzureProxy)

## 关于本项目

AzureProxy 是 [PaperMC/Velocity](https://github.com/PaperMC/Velocity) 的下游（版本基线与上游 `dev/4.0.0` 同步），当前基线：
[`4772ca3`](https://github.com/PaperMC/Velocity/commit/4772ca3022c49bfab37c703f72cbca7654fb5848)（`dev/4.0.0` 头，Velocity 4.1.0-SNAPSHOT）。

项目仓库本身只持有**构建驱动 + 补丁 + 文档**；上游源码在构建时按固定 ref 克隆到 `build/velocity-src/`（与 AzureBranches 的 `folia-server/build/folia-src/` 同构），因此上游演进不会污染 AzureProxy 自身的历史。

### 当前适配内容（v1 构建管线）

- **版本同步**：`build.gradle.kts` 顶部 `velocityRef` 固定上游 ref；`cloneVelocity` 对已存在的克隆做 HEAD 校验（漂移即构建失败）；提升上游时按 README「版本同步」流程显式 re-baseline。
- **品牌适配**：`buildVelocity` 对 `proxy/build.gradle.kts` 做 fail-fast 唯一锚点替换 —— `Implementation-Title`/`Implementation-Vendor` 改为 `AzureProxy`（`VelocityServer.getVersion()` 读取 Manifest 后，启动横幅为 `Booting up AzureProxy <version>...`）。
- **构建管线**：`azurepatches-src`（整文件覆盖，fail-fast 校验目标存在）+ `azurepatches-new`（新增文件），在 Velocity 编译前应用。
- **共享 Gradle**：直接复用 AzureBranches 的 Gradle **9.4.1**（wrapper 已 pin；Velocity 默认的 9.6.1 无需下载），JDK 25。

## 构建

```bash
# 一次性：克隆上游（固定 ref）+ 应用 AzureProxy 补丁 + 编译 + 打可运行 jar
./gradlew buildAzureProxyJar

# 分步
./gradlew cloneVelocity        # 克隆/校验固定 ref（幂等）
./gradlew applyAzurePatches    # 应用 azurepatches-src/new
./gradlew buildVelocity        # 品牌补丁 + :velocity-proxy:compileJava（Gradle 9.4.1）
./gradlew buildAzureProxyJar   # :velocity-proxy:shadowJar → build/libs/azureproxy-*.jar
```

产物：`build/libs/azureproxy-*.jar`，运行：`java -jar build/libs/azureproxy-*.jar`。

## 版本同步（re-baseline）

1. `git ls-remote https://github.com/PaperMC/Velocity.git refs/heads/dev/4.0.0` 取新 ref；
2. 更新 `build.gradle.kts` 的 `velocityRef`；
3. 删除 `build/velocity-src/`，重新 `cloneVelocity`；
4. `applyAzurePatches` 的 fail-fast 会指出失效的 overlay 锚点，逐项修复；
5. `buildAzureProxyJar` 全绿后提交（同时记录对应 commit 号到 README）。

## EXP 模式配置化（azureproxy.mode）

呼应 AzureBranches 的 `command_blocks.mode` 三档概念，代理侧提供单一切换：

```toml
[azureproxy]
mode = "SAFE"        # SAFE（默认）| ACCESS | EXP
```

| 档位 | 行为 |
|---|---|
| **SAFE** | 严格上游默认，零改动（缺省值） |
| **ACCESS** | 运维观察：`log-command-executions = true` |
| **EXP** | AzureBranches EXP7 配套：观察项（`log-command-executions = true`）；若未显式配置转发模式则强制 `MODERN`（沿用上游 forwarding-secret 生效校验）。`announce-proxy-commands` 保持上游默认 `true`（保证客户端命令树中 `/server` 可 tab 补全） |

实现：
- `azurepatches-new/.../com/azureproxy/config/AzureProxyMode.java` —— 档位枚举与预设应用（在 nightconfig 绑定**之前**改写原始配置，预设经上游构造器自然生效）；
- `azurepatches-src/.../VelocityConfiguration.java` —— 覆盖层：在 `read()` 的 `PacketLimiterConfig` 绑定后插入 `AzureProxyMode.applyToConfig(...)`（mod 源码由 `gen-velocity-config-overlay.py` 生成）；
- 启动确认行：`[AzureProxy] azureproxy.mode=EXP applied (log-command-executions=true, announce-proxy-commands=false)`。

## 服务器切换课题（已验证）

双后端切换（Velocity 核心功能）在 AzureProxy 上完整实测：

| 验证项 | 结果 |
|---|---|
| `/server arena` 切换 | ✅ 世界差异可辨（不同 seed/地形/出生点） |
| `/server exp7` 切回 | ✅ |
| 世界隔离 | ✅ `/say` 只在本世界广播 |
| 转发身份一致性 | ✅ 跨后端同一 UUID（2b47bbd5-…，现代转发） |
| Op 独立性 | ✅ 每后端各自 ops.json（Velocity 语义） |
| 红色/无补全 | ✅ 子课题 **T1** 已修复：代理命令树注入（EXP preset 强制 `announce-proxy-commands=true`；客户端收到合并树，`/server` tab 补全正常） |

## 目录结构

```
AzureProxy/
├── build.gradle.kts        # 构建驱动（pin ref / 补丁应用 / 品牌 / 打包）
├── azurepatches-src/       # 整文件覆盖层（必须有对应上游文件，fail-fast）
├── azurepatches-new/       # 新增文件（无对应上游文件）
├── build/velocity-src/     # 上游 Velocity 克隆（gitignored，按 ref 固定）
└── README.md
```

## 许可与致谢

上游 [Velocity](https://github.com/PaperMC/Velocity) 以 **GPLv3** 发布，本项目同样以 **GPLv3** 发布（见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE.md)）——与兄弟项目 AzureBranches（Folia 下游，同样 GPLv3）许可证一致。致谢 PaperMC/Velocity 团队（Tux 等）及其贡献者。
