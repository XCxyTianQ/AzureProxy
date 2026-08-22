# NOTICE

## AzureProxy

AzureProxy 是 [PaperMC/Velocity](https://github.com/PaperMC/Velocity) 的派生项目
（GPLv3 下游，与 AzureBranches 并列，同属 AzureCore）。

### 许可证

- 本项目以 **GNU General Public License version 3 (GPLv3)** 发布，许可证全文见 [LICENSE](LICENSE)。
- 上游 Velocity 同样以 GPLv3 发布（上游仓库 LICENSE 与 HEADER.txt），因此整条派生链
  （Velocity → AzureProxy）保持同一许可证，与兄弟项目 AzureBranches（Folia → Paper → Spigot → Bukkit → CraftBukkit
  逐级 GPLv3）完全一致。

### 修改位置

AzureProxy 的修改以如下形式组织（不修改上游克隆本身）：

- `build.gradle.kts` —— 构建驱动：固定上游 ref（`velocityRef`）、`azurepatches-src`/`azurepatches-new`
  应用、品牌补丁（`Implementation-Title`/`Implementation-Vendor` → AzureProxy）、Gradle 9.4.1 共享。
- `azurepatches-src/` —— 整文件覆盖层（针对上游现有文件）。
- `azurepatches-new/` —— 新增文件（`com.azureproxy.*` 包约定）。

### 致谢

谨向 **PaperMC/Velocity 团队（Tux 等）及其全部贡献者**致以敬意——上游的协议栈、命令与插件体系
是 AzureProxy 的基础。本项目在其之上做实验性适配，修改内容遵循 GPLv3 第 5 节"标记修改"要求。
