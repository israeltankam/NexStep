pluginManagement {
    /*
     * Production uses the plugin version declared in build.gradle.kts.
     * This optional override is reserved for diagnostic builds on a machine
     * whose Android Studio cache predates the release toolchain.
     */
    resolutionStrategy {
        eachPlugin {
            if (requested.id.id == "com.android.application") {
                providers.gradleProperty("NEXSTEP_AGP_VERSION").orNull?.let {
                    useModule("com.android.tools.build:gradle:$it")
                }
            }
        }
    }

    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "NexStepMobile"
include(":app")
