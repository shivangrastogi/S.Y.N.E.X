allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
// Some plugins (e.g. vibration) pin an older compileSdk (33) whose transitive
// AndroidX deps demand 34+. Force every Android library subproject up to 36 so
// the AAR-metadata check passes. This afterEvaluate must be registered BEFORE
// the evaluationDependsOn block below (that block triggers evaluation, after
// which afterEvaluate can no longer be added).
subprojects {
    afterEvaluate {
        val android = project.extensions.findByName("android")
                as? com.android.build.gradle.BaseExtension
        if (android != null) {
            val cur = android.compileSdkVersion
                ?.substringAfter("android-")?.toIntOrNull() ?: 0
            if (cur < 36) {
                android.compileSdkVersion(36)
            }
        }
    }
}

subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
