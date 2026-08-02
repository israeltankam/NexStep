[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$failures = [System.Collections.Generic.List[string]]::new()
$checks = 0

function Test-Condition {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    $script:checks += 1
    if (-not $Condition) {
        $script:failures.Add($Message)
    }
}

function Get-ProjectText {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    return Get-Content -LiteralPath (Join-Path $projectRoot $RelativePath) -Raw
}

$requiredFiles = @(
    "settings.gradle.kts",
    "build.gradle.kts",
    "gradle.properties",
    "gradlew",
    "gradlew.bat",
    "gradle/wrapper/gradle-wrapper.jar",
    "gradle/wrapper/gradle-wrapper.properties",
    "app/build.gradle.kts",
    "app/src/main/AndroidManifest.xml",
    "app/src/main/java/tech/scaleag/nexstep/MainActivity.java",
    "app/src/main/java/tech/scaleag/nexstep/data/NexStepApiClient.java",
    "app/src/main/java/tech/scaleag/nexstep/data/PublicConfigurationStore.java",
    "app/src/main/java/tech/scaleag/nexstep/data/SessionStore.java",
    "app/src/main/java/tech/scaleag/nexstep/ui/ConfigurationView.java",
    "app/src/main/java/tech/scaleag/nexstep/ui/MainShellView.java",
    "app/src/main/java/tech/scaleag/nexstep/ui/NextActionView.java",
    "app/src/main/java/tech/scaleag/nexstep/ui/NewLeadView.java",
    "app/src/main/java/tech/scaleag/nexstep/ui/LeadBoardView.java",
    "app/src/main/java/tech/scaleag/nexstep/ui/ActionsView.java",
    "app/src/main/java/tech/scaleag/nexstep/ui/AdminView.java",
    "app/src/main/res/values/strings.xml",
    "app/src/main/res/values-fr/strings.xml",
    "app/src/main/res/xml/network_security_config.xml",
    "app/src/main/res/drawable-nodpi/nexstep_logo.png",
    "app/src/main/res/drawable-nodpi/scaleag_logo.png",
    "supabase/config.toml",
    "supabase/database/20260730_native_mobile_transactions.sql",
    "supabase/functions/nexstep-mobile-api/index.ts",
    "supabase/functions/nexstep-mobile-api/_shared/auth.ts",
    "supabase/functions/nexstep-mobile-api/_shared/read.ts",
    "supabase/functions/nexstep-mobile-api/_shared/write.ts",
    "supabase/tests/crypto_test.ts"
)

foreach ($relativePath in $requiredFiles) {
    Test-Condition `
        -Condition (Test-Path -LiteralPath (Join-Path $projectRoot $relativePath) -PathType Leaf) `
        -Message "Missing required file: $relativePath"
}

# Android resources must all be parseable before Gradle sees them.
$xmlFiles = Get-ChildItem -LiteralPath (Join-Path $projectRoot "app/src/main") -Recurse -Filter "*.xml"
foreach ($xmlFile in $xmlFiles) {
    try {
        [xml](Get-Content -LiteralPath $xmlFile.FullName -Raw) | Out-Null
        Test-Condition $true "Invalid XML: $($xmlFile.FullName)"
    }
    catch {
        Test-Condition $false "Invalid XML: $($xmlFile.FullName) - $($_.Exception.Message)"
    }
}

$manifest = Get-ProjectText "app/src/main/AndroidManifest.xml"
$networkConfig = Get-ProjectText "app/src/main/res/xml/network_security_config.xml"
$mainActivity = Get-ProjectText "app/src/main/java/tech/scaleag/nexstep/MainActivity.java"
$loginView = Get-ProjectText "app/src/main/java/tech/scaleag/nexstep/ui/LoginView.java"
$apiClient = Get-ProjectText "app/src/main/java/tech/scaleag/nexstep/data/NexStepApiClient.java"
$sessionStore = Get-ProjectText "app/src/main/java/tech/scaleag/nexstep/data/SessionStore.java"
$appBuild = Get-ProjectText "app/build.gradle.kts"
$edgeIndex = Get-ProjectText "supabase/functions/nexstep-mobile-api/index.ts"
$edgeAuth = Get-ProjectText "supabase/functions/nexstep-mobile-api/_shared/auth.ts"
$migration = Get-ProjectText "supabase/database/20260730_native_mobile_transactions.sql"
$migrationExecutable = (
    $migration -split "\r?\n" |
        Where-Object { -not $_.TrimStart().StartsWith("--") }
) -join "`n"

Test-Condition ($manifest.Contains("android.permission.INTERNET")) "INTERNET permission is missing."
Test-Condition ($manifest.Contains('android:usesCleartextTraffic="false"')) "Clear-text traffic is not disabled."
Test-Condition ($manifest.Contains('android:allowBackup="false"')) "Android backup must remain disabled."
Test-Condition ($manifest.Contains('android:exported="true"')) "The launcher activity is not explicitly exported."
Test-Condition ($networkConfig.Contains('cleartextTrafficPermitted="false"')) "Network policy allows clear-text traffic."
Test-Condition ($networkConfig.Contains('<certificates src="system"')) "System trust anchors are not configured."
Test-Condition ($mainActivity.Contains("new MainShellView")) "The native application shell is missing."
Test-Condition ($mainActivity.Contains("new LoginView")) "The native login screen is missing."
Test-Condition ($mainActivity.Contains("new ConfigurationView")) "The interactive mobile setup is missing."
Test-Condition ($mainActivity.Contains("connectConfiguration")) "The public-configuration health check is missing."
Test-Condition ($mainActivity.Contains("validateSavedSession")) "Encrypted session restoration is missing."
Test-Condition ($mainActivity.Contains('api.call("identify_login"')) "Two-step PIN identification is missing."
Test-Condition ($mainActivity.Contains("identifyWithLegacyApi")) "Login compatibility fallback is missing."
Test-Condition ($mainActivity.Contains("UiKit.scroll(this, loginView)")) "The login screen is not scrollable."
Test-Condition ($loginView.Contains("showPasswordStep")) "Password-mode selection is missing."
Test-Condition ($loginView.Contains("show_login_secrets")) "The login visibility control is missing."
Test-Condition ($loginView.Contains("PasswordTransformationMethod")) "Secret visibility switching is missing."
Test-Condition ($apiClient.Contains("HttpURLConnection")) "The native HTTPS API client is missing."
Test-Condition ($apiClient.Contains("/functions/v1/nexstep-mobile-api")) "The Edge Function endpoint is missing."
Test-Condition ($apiClient.Contains('setRequestProperty("apikey"')) "The public Supabase API key header is missing."
Test-Condition ($sessionStore.Contains("AndroidKeyStore")) "Android Keystore protection is missing."
Test-Condition ($sessionStore.Contains("AES/GCM/NoPadding")) "AES-GCM session encryption is missing."
Test-Condition ($appBuild.Contains("checkNoDatabaseSecrets")) "The server-secret build guard is missing."
Test-Condition ($appBuild.Contains("SUPABASE_PROJECT_URL")) "The public Supabase URL build setting is missing."
Test-Condition ($appBuild.Contains("SUPABASE_PUBLISHABLE_KEY")) "The public Supabase key build setting is missing."
Test-Condition ($appBuild.Contains("minSdk = 29")) "minSdk must be 29."
Test-Condition ($appBuild.Contains('VERSION_17')) "Java 17 compilation is not configured."
Test-Condition ($appBuild.Contains("releaseSigningReady")) "Environment-only release signing is missing."
Test-Condition ($edgeIndex.Contains("Deno.serve")) "The Edge Function request handler is missing."
Test-Condition ($edgeIndex.Contains("authenticate(db, request)")) "Authenticated Edge Function routing is missing."
Test-Condition ($edgeIndex.Contains('operation === "identify_login"')) "PIN identification routing is missing."
Test-Condition ($edgeAuth.Contains("auth_sessions")) "Revocable server-side sessions are missing."
Test-Condition ($edgeAuth.Contains("auth_attempts")) "Authentication rate limiting is missing."
Test-Condition ($edgeAuth.Contains("identifyLogin")) "Password-mode identification is missing."
Test-Condition ($edgeIndex.Contains("pendingPasswordResets")) "Password-reset inbox routing is missing."
Test-Condition ($edgeAuth.Contains("is_global_admin")) "Global administrator authentication is missing."
Test-Condition `
    ((Get-ProjectText "supabase/functions/nexstep-mobile-api/_shared/read.ts").Contains(
        "organizationName"
    )) `
    "Global password-reset requests do not identify their organization."
Test-Condition `
    ((Get-ProjectText "supabase/functions/nexstep-mobile-api/_shared/write.ts").Contains(
        "requestOrganizationId"
    )) `
    "Cross-organization global reset review is missing."
Test-Condition ($migration.Contains("SECURITY DEFINER")) "Transactional mobile SQL functions are missing."
Test-Condition ($migration.Contains("REVOKE ALL")) "Public execution rights are not revoked."
Test-Condition ($migration.Contains("GRANT EXECUTE")) "Service-role execution rights are missing."
Test-Condition `
    ($migrationExecutable.IndexOf("DROP TABLE", [System.StringComparison]::OrdinalIgnoreCase) -lt 0) `
    "The additive migration drops a table."
Test-Condition `
    ($migrationExecutable.IndexOf("TRUNCATE", [System.StringComparison]::OrdinalIgnoreCase) -lt 0) `
    "The additive migration truncates data."
Test-Condition `
    ($migrationExecutable.IndexOf("ALTER TABLE", [System.StringComparison]::OrdinalIgnoreCase) -lt 0) `
    "The additive migration alters a table."
Test-Condition `
    ($migrationExecutable.IndexOf("DELETE FROM", [System.StringComparison]::OrdinalIgnoreCase) -lt 0) `
    "The additive migration deletes data."

# English and French catalogs must expose exactly the same strings and plurals.
[xml]$englishStrings = Get-ProjectText "app/src/main/res/values/strings.xml"
[xml]$frenchStrings = Get-ProjectText "app/src/main/res/values-fr/strings.xml"
$englishKeys = @($englishStrings.resources.string | ForEach-Object { $_.name } | Sort-Object)
$frenchKeys = @($frenchStrings.resources.string | ForEach-Object { $_.name } | Sort-Object)
$englishPluralKeys = @($englishStrings.resources.plurals | ForEach-Object { $_.name } | Sort-Object)
$frenchPluralKeys = @($frenchStrings.resources.plurals | ForEach-Object { $_.name } | Sort-Object)
Test-Condition (($englishKeys -join "|") -eq ($frenchKeys -join "|")) "English and French string keys differ."
Test-Condition (($englishPluralKeys -join "|") -eq ($frenchPluralKeys -join "|")) "English and French plural keys differ."
Test-Condition ($englishKeys.Count -ge 100) "The native interface is not sufficiently internationalized."

$requiredUrgencyKeys = @(
    "urgency_red",
    "urgency_yellow",
    "urgency_green",
    "urgency_blue",
    "urgency_gray"
)
foreach ($key in $requiredUrgencyKeys) {
    Test-Condition ($englishKeys -contains $key) "Missing English urgency label: $key"
    Test-Condition ($frenchKeys -contains $key) "Missing French urgency label: $key"
}

# Every referenced Android string must exist in both languages.
$javaFiles = Get-ChildItem -LiteralPath (Join-Path $projectRoot "app/src/main/java") -Recurse -Filter "*.java"
$referencedKeys = @(
    $javaFiles |
        ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw } |
        ForEach-Object { [regex]::Matches($_, '(?<!android\.)R\.string\.([A-Za-z0-9_]+)') } |
        ForEach-Object { $_.Groups[1].Value } |
        Sort-Object -Unique
)
foreach ($key in $referencedKeys) {
    Test-Condition ($englishKeys -contains $key) "Java references missing English string: $key"
    Test-Condition ($frenchKeys -contains $key) "Java references missing French string: $key"
}
$referencedPluralKeys = @(
    $javaFiles |
        ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw } |
        ForEach-Object { [regex]::Matches($_, 'R\.plurals\.([A-Za-z0-9_]+)') } |
        ForEach-Object { $_.Groups[1].Value } |
        Sort-Object -Unique
)
foreach ($key in $referencedPluralKeys) {
    Test-Condition ($englishPluralKeys -contains $key) "Java references missing English plural: $key"
    Test-Condition ($frenchPluralKeys -contains $key) "Java references missing French plural: $key"
}

# Server-only values and the former browser shell must never enter packaged files.
$forbiddenMarkers = @(
    ("postgres" + "ql://"),
    "postgres://",
    ("DATABASE" + "_URL"),
    ("APP_PIN" + "_PEPPER"),
    ("SUPABASE" + "_DB_PASSWORD"),
    ("SUPABASE" + "_SERVICE_ROLE_KEY"),
    ("sb_" + "secret_"),
    ("NEXSTEP" + "_APP_URL"),
    ("android.webkit." + "WebView"),
    ("streamlit" + ".app")
)
$packagedTextFiles = Get-ChildItem -LiteralPath (Join-Path $projectRoot "app/src") -Recurse -File |
    Where-Object { $_.Extension -in @(".java", ".xml", ".json", ".html", ".txt") }

foreach ($file in $packagedTextFiles) {
    $content = Get-Content -LiteralPath $file.FullName -Raw
    foreach ($marker in $forbiddenMarkers) {
        Test-Condition `
            -Condition ($content.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) `
            -Message "Forbidden marker '$marker' found in $($file.FullName)."
    }
}

Test-Condition `
    ((Get-Item -LiteralPath (Join-Path $projectRoot "gradle/wrapper/gradle-wrapper.jar")).Length -gt 30KB) `
    "The Gradle wrapper JAR is unexpectedly small."
foreach ($logo in @("nexstep_logo.png", "scaleag_logo.png")) {
    Test-Condition `
        ((Get-Item -LiteralPath (Join-Path $projectRoot "app/src/main/res/drawable-nodpi/$logo")).Length -gt 1KB) `
        "Logo is missing or empty: $logo"
}

if ($failures.Count -gt 0) {
    Write-Host "Mobile project validation failed: $($failures.Count) error(s)." -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host " - $failure" -ForegroundColor Red
    }
    exit 1
}

Write-Host "Mobile project validation passed: $checks checks." -ForegroundColor Green
