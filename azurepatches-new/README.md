# azurepatches-new —— 新增文件

与 AzureBranches 同构：本目录下的文件按相对路径**新增**到 `build/velocity-src/` 中
（在 `applyAzurePatches` 应用），用于上游不存在的新类（如 `com.azureproxy.*` 包）。

约定：
- 新增包前缀使用 `com.azureproxy.*`（与 AzureBranches 的 `com.azurebranches.*` 对应）；
- 保持与上游一致的代码风格与许可头（头文件格式见上游 `HEADER.txt` / 各源文件）；
- 上游文件冲突时优先用 `azurepatches-src` 覆盖而不是改依赖方。
