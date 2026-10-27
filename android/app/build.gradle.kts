plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

abstract class GenerateRustBindings : Exec() {
    @get:OutputDirectory
    abstract val outputDirectory: DirectoryProperty
}

val generateRustBindings = tasks.register<GenerateRustBindings>("generateRustBindings") {
    workingDir(rootProject.projectDir.parentFile)
    commandLine("bash", "scripts/android/generate-bindings.sh")
    inputs.files(fileTree("../../engine/ffi/src"), file("../../engine/ffi/Cargo.toml"),
        file("../../engine/ffi/uniffi.toml"), file("../../engine/Cargo.lock"),
        file("../../scripts/android/generate-bindings.sh"))
    outputDirectory.set(layout.buildDirectory.dir("generated/uniffi"))
}

val buildRust = tasks.register<Exec>("buildRust") {
    dependsOn(generateRustBindings)
    workingDir(rootProject.projectDir.parentFile)
    commandLine("bash", "scripts/android/build-rust.sh")
    inputs.files(fileTree("../../engine") {
        include("**/*.rs", "**/Cargo.toml", "Cargo.lock")
        exclude("target/**")
    }, file("../../scripts/android/build-rust.sh"))
    outputs.dir("src/main/jniLibs")
}

tasks.named("preBuild") { dependsOn(buildRust) }

android {
    namespace = "com.flexweek.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.flexweek.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 4
        versionName = "1.2.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }


    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

androidComponents.onVariants { variant ->
    variant.sources.java?.addGeneratedSourceDirectory(generateRustBindings) { it.outputDirectory }
}

dependencies {
    implementation("${libs.jna.get()}@aar")
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.androidx.work.runtime.ktx)
    debugImplementation(libs.compose.ui.tooling.preview)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation("org.json:json:20240303")
}
