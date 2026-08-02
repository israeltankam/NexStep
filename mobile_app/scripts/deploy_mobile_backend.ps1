[CmdletBinding()]
param(
    [ValidatePattern("^[a-z0-9]{20}$")]
    [string]$ProjectRef = "smfpnijhmdajaezvxdit"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertFrom-SecureValue {
    param(
        [Parameter(Mandatory)]
        [Security.SecureString]$Value
    )

    return [System.Net.NetworkCredential]::new("", $Value).Password
}

function Invoke-SupabaseCli {
    param(
        [Parameter(Mandatory)]
        [string[]]$CliArguments
    )

    & $script:NpxCommand --yes supabase@latest @CliArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Supabase CLI failed with exit code $LASTEXITCODE."
    }
}

$scriptDirectory = Split-Path -Parent $PSCommandPath
$mobileDirectory = Split-Path -Parent $scriptDirectory
$migrationPath = Join-Path `
    $mobileDirectory `
    "supabase\database\20260730_native_mobile_transactions.sql"
$projectUrl = "https://$ProjectRef.supabase.co"
$functionUrl = "$projectUrl/functions/v1/nexstep-mobile-api"

if (-not (Test-Path -LiteralPath $migrationPath -PathType Leaf)) {
    throw "Mobile database migration not found: $migrationPath"
}

$npx = Get-Command "npx.cmd" -ErrorAction SilentlyContinue
if (-not $npx) {
    throw "Node.js/npm is required because npx.cmd is missing."
}
$script:NpxCommand = $npx.Source

# Keep TLS verification enabled while allowing Node.js to trust Windows CAs.
$previousNodeOptions = $env:NODE_OPTIONS
if ($env:NODE_OPTIONS -notlike "*--use-system-ca*") {
    $env:NODE_OPTIONS = ($env:NODE_OPTIONS, "--use-system-ca" -join " ").Trim()
}

$plainPepper = $null
$publishableKey = $null
$securePepper = $null
$securePublishableKey = $null

try {
    Write-Host ""
    Write-Host "NexStep Mobile - Supabase backend deployment" -ForegroundColor Cyan
    Write-Host "Project: $ProjectRef"
    Write-Host ""
    Write-Host "This procedure deploys one Edge Function and one server secret."
    Write-Host "It does not delete, truncate, replace, or export database data."
    Write-Host ""
    Write-Host "Before continuing, run this additive SQL file in Supabase SQL Editor:"
    Write-Host $migrationPath -ForegroundColor Yellow
    Write-Host ""

    $migrationConfirmation = Read-Host `
        "Type SQL-OK only after Supabase reported Success"
    if ($migrationConfirmation.Trim() -cne "SQL-OK") {
        Write-Warning "Deployment cancelled. Run the SQL file, then start this script again."
        exit 2
    }

    Write-Host "Checking the current Supabase CLI..."
    Invoke-SupabaseCli -CliArguments @("--version")

    Write-Host ""
    Write-Host "Supabase authentication will now open in your browser."
    Invoke-SupabaseCli -CliArguments @("login")

    Write-Host ""
    Write-Host "Paste the existing APP_PIN_PEPPER from Streamlit Cloud."
    Write-Host "The characters remain hidden and the value is never written to a file."
    $securePepper = Read-Host "APP_PIN_PEPPER" -AsSecureString
    $plainPepper = ConvertFrom-SecureValue -Value $securePepper
    if ($plainPepper.Length -lt 32) {
        throw "APP_PIN_PEPPER is unexpectedly short. Use the existing Streamlit secret."
    }

    Invoke-SupabaseCli -CliArguments @(
        "secrets",
        "set",
        "APP_PIN_PEPPER=$plainPepper",
        "--project-ref",
        $ProjectRef
    )

    Write-Host ""
    Write-Host "Deploying nexstep-mobile-api..."
    Invoke-SupabaseCli -CliArguments @(
        "functions",
        "deploy",
        "nexstep-mobile-api",
        "--project-ref",
        $ProjectRef,
        "--no-verify-jwt",
        "--use-api",
        "--workdir",
        $mobileDirectory
    )

    Write-Host ""
    Write-Host "Paste this project's public Publishable key to test the deployment."
    $securePublishableKey = Read-Host "Publishable key" -AsSecureString
    $publishableKey = ConvertFrom-SecureValue -Value $securePublishableKey
    if (
        -not $publishableKey.StartsWith("sb_publishable_") -and
        -not $publishableKey.StartsWith("eyJ")
    ) {
        throw "This is not a Supabase Publishable key."
    }

    $headers = @{
        apikey = $publishableKey
        "Content-Type" = "application/json"
    }
    $body = @{
        operation = "health"
        payload = @{}
    } | ConvertTo-Json -Depth 3

    $health = Invoke-RestMethod `
        -Method Post `
        -Uri $functionUrl `
        -Headers $headers `
        -Body $body

    if (-not $health.ok -or $health.data.status -ne "ok") {
        throw "The Edge Function responded, but its health result is invalid."
    }

    Write-Host ""
    Write-Host "[OK] NexStep Mobile backend is deployed and healthy." -ForegroundColor Green
    Write-Host "Return to the phone and tap Check and continue again."
}
finally {
    # Remove sensitive values from this PowerShell process as soon as possible.
    $plainPepper = $null
    $publishableKey = $null
    $securePepper = $null
    $securePublishableKey = $null
    $env:NODE_OPTIONS = $previousNodeOptions
}
