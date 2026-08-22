# azurepatches-src —— 整文件覆盖层

与 AzureBranches 同构：本目录下的文件按相对路径**整文件覆盖**到 `build/velocity-src/` 中的
同名上游文件（在 `applyAzurePatches` 应用）。

约定：
- 覆盖目标必须存在（fail-fast：上游布局变化时构建直接报“无对应上游文件”，不会静默丢包）；
- 适用于：需要修改多个位置的现有文件（如 `proxy/src/main/java/.../VelocityServer.java`）；
- 保持与上游一致的代码风格（4 空格缩进、spotless/checkstyle 可通过构建验证）；
- 每次 re-baseline（bump `velocityRef`）后运行 `./gradlew applyAzurePatches` 验证锚点。
