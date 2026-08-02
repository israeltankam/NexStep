[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Debug",

    [string]$SupabaseUrl = $env:NEXSTEP_SUPABASE_URL,

    [string]$PublishableKey = $env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY,

    [ValidateRange(29, 99)]
    [int]$CompileSdk = 36,

    [ValidateRange(29, 99)]
    [int]$TargetSdk = 36
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ($TargetSdk -gt $CompileSdk) {
    throw "TargetSdk cannot be newer than CompileSdk."
}
if ([string]::IsNullOrWhiteSpace($SupabaseUrl)) {
    $SupabaseUrl = "https://smfpnijhmdajaezvxdit.supabase.co"
}
if ([string]::IsNullOrWhiteSpace($PublishableKey)) {
    if ($Configuration -eq "Release") {
        throw "PublishableKey is required for Release. Use sb_publishable_..., never a secret key."
    }
    $PublishableKey = "YOUR_PUBLISHABLE_KEY"
    Write-Host `
        "No public key embedded: the Debug APK will show the one-time mobile setup form." `
        -ForegroundColor Yellow
}

$parsedUrl = [System.Uri]$SupabaseUrl
if ($parsedUrl.Scheme -ne "https" -or $parsedUrl.UserInfo) {
    throw "SupabaseUrl must be the public HTTPS Project URL without credentials."
}
$isPlaceholderKey = $PublishableKey -eq "YOUR_PUBLISHABLE_KEY"
if (-not $isPlaceholderKey -and
    -not $PublishableKey.StartsWith("sb_publishable_") -and
    -not $PublishableKey.StartsWith("eyJ")) {
    throw "PublishableKey must be the public Supabase publishable/legacy anon key."
}
if (-not $isPlaceholderKey -and (
    $PublishableKey.StartsWith("sb_secret_") -or
    $PublishableKey -match "service[_-]?role"
)) {
    throw "A secret/service-role key must never be embedded in an APK."
}

# Prefer Android Studio's bundled Java runtime.
$androidStudioJdk = "C:\Program Files\Android\Android Studio\jbr"
if (Test-Path -LiteralPath (Join-Path $androidStudioJdk "bin\javac.exe")) {
    $env:JAVA_HOME = $androidStudioJdk
}
elseif (-not $env:JAVA_HOME -or -not (Test-Path (Join-Path $env:JAVA_HOME "bin\javac.exe"))) {
    throw "JDK 17 not found. Install Android Studio or define JAVA_HOME."
}

if (-not $env:ANDROID_HOME) {
    $env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA "Android\Sdk"
}
if (-not (Test-Path -LiteralPath $env:ANDROID_HOME)) {
    throw "Android SDK not found. Install it from Android Studio SDK Manager."
}

$requiredPlatform = Join-Path $env:ANDROID_HOME "platforms\android-$CompileSdk"
if (-not (Test-Path -LiteralPath $requiredPlatform)) {
    throw "Android SDK Platform $CompileSdk is missing. Install it from Android Studio SDK Manager."
}

$env:NEXSTEP_SUPABASE_URL = $SupabaseUrl.Trim()
$env:NEXSTEP_SUPABASE_PUBLISHABLE_KEY = $PublishableKey.Trim()
$env:GRADLE_USER_HOME = Join-Path $projectRoot ".gradle-user-home"
$env:ANDROID_USER_HOME = Join-Path $projectRoot ".android-user-home"
Remove-Item Env:ANDROID_PREFS_ROOT -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $env:GRADLE_USER_HOME -Force | Out-Null
New-Item -ItemType Directory -Path $env:ANDROID_USER_HOME -Force | Out-Null

<#
Avast HTTPS inspection can use a Windows root certificate unknown to Java.
This creates a private, ignored trust store without touching the system JDK.
#>
$avastCertificate = Get-ChildItem `
    -Path Cert:\CurrentUser\Root, Cert:\LocalMachine\Root `
    -ErrorAction SilentlyContinue |
    Where-Object { $_.Subject -match "Avast Web/Mail Shield Root" } |
    Select-Object -First 1

if ($avastCertificate) {
    $trustDirectory = Join-Path $env:GRADLE_USER_HOME "trust"
    $trustStore = Join-Path $trustDirectory "nexstep-cacerts"
    $certificateFile = Join-Path $trustDirectory "avast-web-shield.cer"
    $javaTrustStore = Join-Path $env:JAVA_HOME "lib\security\cacerts"
    $keytool = Join-Path $env:JAVA_HOME "bin\keytool.exe"

    New-Item -ItemType Directory -Path $trustDirectory -Force | Out-Null
    Copy-Item -LiteralPath $javaTrustStore -Destination $trustStore -Force
    Export-Certificate -Cert $avastCertificate -FilePath $certificateFile -Force | Out-Null
    & $keytool `
        -importcert `
        -noprompt `
        -trustcacerts `
        -alias "nexstep-avast-web-shield" `
        -file $certificateFile `
        -keystore $trustStore `
        -storepass "changeit" |
        Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to prepare the temporary Java trust store."
    }

    $normalizedTrustStore = $trustStore.Replace("\", "/")
    $env:GRADLE_OPTS =
        "-Djavax.net.ssl.trustStore=$normalizedTrustStore " +
        "-Djavax.net.ssl.trustStorePassword=changeit"
}

if ($Configuration -eq "Release") {
    foreach ($variableName in @(
        "NEXSTEP_KEYSTORE_PATH",
        "NEXSTEP_KEYSTORE_PASSWORD",
        "NEXSTEP_KEY_ALIAS",
        "NEXSTEP_KEY_PASSWORD"
    )) {
        if (-not [System.Environment]::GetEnvironmentVariable($variableName)) {
            throw "$variableName is required for a signed release APK."
        }
    }
}

Write-Host "Validating NexStep Mobile..." -ForegroundColor Cyan
& powershell `
    -ExecutionPolicy Bypass `
    -File (Join-Path $PSScriptRoot "validate_mobile_project.ps1")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$variant = $Configuration.ToLowerInvariant()
$gradleArguments = @(
    "-PNEXSTEP_COMPILE_SDK=$CompileSdk",
    "-PNEXSTEP_TARGET_SDK=$TargetSdk",
    "--console=plain",
    "--no-daemon",
    "checkNoDatabaseSecrets",
    "lint$Configuration",
    "assemble$Configuration"
)

Write-Host "Building the native NexStep Mobile $Configuration APK..." -ForegroundColor Cyan
Push-Location $projectRoot
try {
    & (Join-Path $projectRoot "gradlew.bat") @gradleArguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

$apkName = if ($Configuration -eq "Release") { "app-release.apk" } else { "app-debug.apk" }
$apkPath = Join-Path $projectRoot "app\build\outputs\apk\$variant\$apkName"
if (-not (Test-Path -LiteralPath $apkPath)) {
    throw "Gradle finished without creating the expected APK."
}

$apk = Get-Item -LiteralPath $apkPath
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $apkPath
Write-Host "Native APK ready: $($apk.FullName)" -ForegroundColor Green
Write-Host "Size: $($apk.Length) bytes"
Write-Host "SHA-256: $($hash.Hash)"
