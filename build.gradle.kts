// AzureProxy build driver
// 上游 Velocity 固定在 build/velocity-src（与 AzureBranches 的 folia-src 同构）。
// 仓库本身只持有：构建驱动 + azurepatches-src/new + 文档。上游漂移时显式 re-baseline。
import java.io.File

val velocityRepo = "https://github.com/PaperMC/Velocity.git"
// 固定上游 ref（dev/4.0.0 头）。升级流程：1) bump 此值 2) 删除 build/velocity-src
// 3) 重新 cloneVelocity + applyAzurePatches，手工修 overlay 冲突 4) build 验证。
val velocityRef = "4772ca3022c49bfab37c703f72cbca7654fb5848"
val velocityDir = file("build/velocity-src")

fun sh(dir: File? = null, vararg cmd: String): Int {
    val pb = ProcessBuilder(*cmd).redirectErrorStream(true)
    if (dir != null) pb.directory(dir)
    val p = pb.start(); p.inputStream.transferTo(System.out); return p.waitFor()
}

fun gw(dir: File): String =
    if (System.getProperty("os.name").lowercase().contains("win")) "gradlew.bat" else "./gradlew"

/** fail-fast 唯一匹配替换：上游漂移（锚点缺失/重复）直接打断构建。 */
fun transformSource(file: File, label: String, old: String, to: String) {
    val normalized = file.readText().replace("\r\n", "\n")
    val oldNorm = old.replace("\r\n", "\n")
    val count = Regex(Regex.escape(oldNorm)).findAll(normalized).count()
    check(count > 0) { "[$label] anchor not found in ${file.path} (upstream drift?)" }
    check(count == 1) { "[$label] anchor matched $count times in ${file.path}" }
    file.writeText(normalized.replace(oldNorm, to))
    println("  [$label] transformed (1 anchor)")
}

/** 用 AzureBranches 共享的 Gradle 9.4.1（9.6.1 需额外下载 130MB，无必要）。 */
fun ensureWrapperPinned() {
    val wrapperProps = File(velocityDir, "gradle/wrapper/gradle-wrapper.properties")
    val props = wrapperProps.readText()
    if ("gradle-9.4.1-bin" !in props) {
        wrapperProps.writeText(props
            .replace(Regex("distributionUrl=.*"), "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.4.1-bin.zip"))
        println("  [wrapper] pinned to Gradle 9.4.1 (AzureBranches shared distribution)")
    }
}

tasks.register("cloneVelocity") {
    doLast {
        if (File(velocityDir, ".git").exists()) {
            val out = java.io.ByteArrayOutputStream()
            val p = ProcessBuilder("git", "rev-parse", "HEAD")
                .directory(velocityDir).redirectErrorStream(true).start()
            p.inputStream.transferTo(out); p.waitFor()
            val head = out.toString().trim()
            check(head == velocityRef) {
                "velocity-src HEAD=$head != pinned $velocityRef — 请按 README「版本同步」执行 re-baseline"
            }
            println("Velocity clone cached at pinned ref $velocityRef")
            return@doLast
        }
        velocityDir.parentFile.mkdirs()
        check(sh(cmd = *arrayOf("git", "init", velocityDir.absolutePath)) == 0) { "git init failed" }
        check(sh(dir = velocityDir, cmd = *arrayOf("git", "remote", "add", "origin", velocityRepo)) == 0) { "remote add failed" }
        check(sh(dir = velocityDir, cmd = *arrayOf("git", "fetch", "--depth", "1", "origin", velocityRef)) == 0) { "git fetch failed" }
        check(sh(dir = velocityDir, cmd = *arrayOf("git", "checkout", "--detach", "FETCH_HEAD")) == 0) { "git checkout failed" }
        check(sh(dir = velocityDir, cmd = *arrayOf("git", "rev-parse", "HEAD")) == 0) { "rev-parse failed" }
        println("Velocity cloned at pinned ref $velocityRef")
    }
}

tasks.register("applyAzurePatches") {
    dependsOn("cloneVelocity")
    doLast {
        val overrideSrc = file("azurepatches-src")
        if (overrideSrc.exists() && overrideSrc.isDirectory) {
            // fail-fast：overlay 文件必须有对应上游文件
            overrideSrc.walkTopDown().filter { it.isFile }.forEach { f ->
                check(File(velocityDir, f.relativeTo(overrideSrc).path).exists()) {
                    "azurepatches-src overlay 无对应上游文件: ${f.relativeTo(overrideSrc).path}"
                }
            }
            overrideSrc.walkTopDown().filter { it.isFile }.forEach { f ->
                f.copyTo(File(velocityDir, f.relativeTo(overrideSrc).path), overwrite = true)
            }
            println("  Overlaid azurepatches-src/**")
        }
        val newSrc = file("azurepatches-new")
        if (newSrc.exists() && newSrc.isDirectory) {
            newSrc.walkTopDown().filter { it.isFile }.forEach { f ->
                f.copyTo(File(velocityDir, f.relativeTo(newSrc).path), overwrite = true)
            }
            println("  Added azurepatches-new/**")
        }
    }
}

tasks.register("buildVelocity") {
    dependsOn("applyAzurePatches")
    doLast {
        // AzureProxy 品牌：启动横幅 (Booting up <name> <version>...) 读取 Jar Manifest 的
        // Implementation-Title/Vendor（VelocityServer.getVersion）。
        val proxyBuild = File(velocityDir, "proxy/build.gradle.kts")
        transformSource(proxyBuild, "proxy/build.gradle.kts (brand title)",
            "attributes[\"Implementation-Title\"] = \"Velocity\"",
            "attributes[\"Implementation-Title\"] = \"AzureProxy\"")
        transformSource(proxyBuild, "proxy/build.gradle.kts (brand vendor)",
            "attributes[\"Implementation-Vendor\"] = \"Velocity Contributors\"",
            "attributes[\"Implementation-Vendor\"] = \"AzureProxy Contributors\"")

        ensureWrapperPinned()

        val g = gw(velocityDir)
        check(sh(dir = velocityDir, cmd = *arrayOf(g, ":velocity-proxy:compileJava", "--no-configuration-cache")) == 0) {
            "velocity compile failed"
        }
        println("AzureProxy build ok (Velocity ref=$velocityRef, Gradle 9.4.1)")
    }
}

tasks.register("buildAzureProxyJar") {
    dependsOn("buildVelocity")
    doLast {
        val g = gw(velocityDir)
        check(sh(dir = velocityDir, cmd = *arrayOf(g, ":velocity-proxy:shadowJar", "--no-configuration-cache")) == 0) {
            "shadowJar failed"
        }
        val libs = File(velocityDir, "proxy/build/libs")
        val jar = libs.listFiles()?.filter { it.name.endsWith(".jar") && !it.name.endsWith("-sources.jar") && !it.name.endsWith("-javadoc.jar") }?.maxByOrNull { it.length() }
            ?: error("shadowJar artifact not found in $libs")
        val dest = layout.buildDirectory.file("libs/${jar.name.replace("velocity-", "azureproxy-")}")
        dest.get().asFile.parentFile.mkdirs()
        jar.copyTo(dest.get().asFile, overwrite = true)
        println("Done: ${dest.get().asFile} (${dest.get().asFile.length() / 1024 / 1024} MB)")
        println("Run: java -jar ${dest.get().asFile.absolutePath}")
    }
}

tasks.build { dependsOn("buildAzureProxyJar") }
