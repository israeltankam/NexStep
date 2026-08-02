import java.net.URI

plugins {
    id("com.android.application")
}

/*
 * Both values below are public Supabase client settings. PostgreSQL URLs,
 * secret/service-role keys and the PIN pepper remain server-side.
 */
val supabaseProjectUrl = providers.gradleProperty("NEXSTEP_SUPABASE_URL")
    .orElse(providers.environmentVariable("NEXSTEP_SUPABASE_URL"))
    .orElse("https://smfpnijhmdajaezvxdit.supabase.co")
    .get()
    .trim()
val supabasePublishableKey = providers.gradleProperty("NEXSTEP_SUPABASE_PUBLISHABLE_KEY")
    .orElse(providers.environmentVariable("NEXSTEP_SUPABASE_PUBLISHABLE_KEY"))
    .orElse("YOUR_PUBLISHABLE_KEY")
    .get()
    .trim()

val parsedSupabaseUrl = URI(supabaseProjectUrl)
require(parsedSupabaseUrl.scheme.equals("https", ignoreCase = true)) {
    "NEXSTEP_SUPABASE_URL must use HTTPS."
}
require(!parsedSupabaseUrl.host.isNullOrBlank() && parsedSupabaseUrl.userInfo == null) {
    "NEXSTEP_SUPABASE_URL must be a public URL without embedded credentials."
}
require(
    supabasePublishableKey == "YOUR_PUBLISHABLE_KEY" ||
        supabasePublishableKey.startsWith("sb_publishable_") ||
        supabasePublishableKey.startsWith("eyJ")
) {
    "Use the Supabase publishable key, never a secret/service-role key."
}

/*
 * API 36 is the release default. Explicit overrides exist only so an older
 * local SDK can compile a diagnostic APK without changing tracked files.
 */
val compileSdkVersion = providers.gradleProperty("NEXSTEP_COMPILE_SDK")
    .orElse("36")
    .get()
    .toInt()
val targetSdkVersion = providers.gradleProperty("NEXSTEP_TARGET_SDK")
    .orElse("36")
    .get()
    .toInt()
require(targetSdkVersion <= compileSdkVersion) {
    "NEXSTEP_TARGET_SDK cannot be newer than NEXSTEP_COMPILE_SDK."
}

/*
 * Release signing is optional during development and is supplied entirely by
 * environment variables. Keystores and passwords therefore stay outside Git.
 */
val releaseSigningValues = mapOf(
    "storePath" to providers.environmentVariable("NEXSTEP_KEYSTORE_PATH").orNull,
    "storePassword" to providers.environmentVariable("NEXSTEP_KEYSTORE_PASSWORD").orNull,
    "keyAlias" to providers.environmentVariable("NEXSTEP_KEY_ALIAS").orNull,
    "keyPassword" to providers.environmentVariable("NEXSTEP_KEY_PASSWORD").orNull,
)
val releaseSigningReady = releaseSigningValues.values.all { !it.isNullOrBlank() }

android {
    namespace = "tech.scaleag.nexstep"
    compileSdk = compileSdkVersion

    defaultConfig {
        applicationId = "tech.scaleag.nexstep"
        minSdk = 29
        targetSdk = targetSdkVersion
        versionCode = 4
        versionName = "1.0.3"

        val escapedUrl = supabaseProjectUrl
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
        val escapedKey = supabasePublishableKey
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
        buildConfigField("String", "SUPABASE_PROJECT_URL", "\"$escapedUrl\"")
        buildConfigField("String", "SUPABASE_PUBLISHABLE_KEY", "\"$escapedKey\"")
    }

    signingConfigs {
        if (releaseSigningReady) {
            create("release") {
                storeFile = file(releaseSigningValues.getValue("storePath")!!)
                storePassword = releaseSigningValues.getValue("storePassword")
                keyAlias = releaseSigningValues.getValue("keyAlias")
                keyPassword = releaseSigningValues.getValue("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            if (releaseSigningReady) {
                signingConfig = signingConfigs.getByName("release")
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures {
        buildConfig = true
    }

    bundle {
        // Both built-in languages must remain available to the runtime switcher.
        language {
            enableSplit = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        abortOnError = true
        checkReleaseBuilds = true
        // The wrapper is pinned to the version validated with AGP 9.0.1.
        disable += "AndroidGradlePluginVersion"
    }
}

/*
 * This pre-build audit deliberately scans packaged source and resources.
 * It prevents a future edit from placing server credentials inside the APK.
 */
val checkNoDatabaseSecrets by tasks.registering {
    group = "verification"
    description = "Fails if server-only secrets are present in packaged mobile files."

    doLast {
        val forbiddenMarkers = listOf(
            "postgres" + "ql://",
            "postgres://",
            "DATABASE" + "_URL",
            "APP_PIN" + "_PEPPER",
            "SUPABASE" + "_DB_PASSWORD",
            "SUPABASE" + "_SERVICE_ROLE_KEY",
            "sb_" + "secret_",
            "NEXSTEP" + "_APP_URL",
            "android.webkit." + "WebView",
        )
        val packagedFiles = fileTree("src") {
            include("**/*.java", "**/*.xml", "**/*.json", "**/*.html", "**/*.txt")
        }

        packagedFiles.forEach { file ->
            val content = file.readText(Charsets.UTF_8)
            forbiddenMarkers.forEach { marker ->
                check(!content.contains(marker, ignoreCase = true)) {
                    "Server-only marker '$marker' found in ${file.relativeTo(projectDir)}."
                }
            }
        }
    }
}

tasks.matching { it.name == "preBuild" }.configureEach {
    dependsOn(checkNoDatabaseSecrets)
}
