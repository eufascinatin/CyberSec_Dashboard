param(
    [switch]$Unattended
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " CyberSec Dashboard Setup Utility" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

function Refresh-EnvironmentPath {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::Machine)
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::User)
    $env:Path = "$machinePath;$userPath"
}

function Test-Winget {
    if (-not (Get-Command "winget.exe" -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: Windows Package Manager (winget) was not found." -ForegroundColor Red
        Write-Host "Install/update Microsoft App Installer and run this setup again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "[OK] winget detected." -ForegroundColor Green
}

function Get-PythonInfo {
    Refresh-EnvironmentPath

    foreach ($name in @("python.exe", "py.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            try {
                $version = & $cmd.Source --version 2>&1
                if ($LASTEXITCODE -eq 0 -and "$version" -match "Python\s+\d") {
                    return @{
                        Installed = $true
                        Command   = $cmd.Source
                        Version   = "$version"
                    }
                }
            } catch {}
        }
    }

    return @{ Installed = $false; Command = $null; Version = $null }
}

function Find-MongoExecutable {
    Refresh-EnvironmentPath

    $mongo = Get-Command "mongod.exe" -ErrorAction SilentlyContinue
    if ($mongo) {
        return $mongo.Source
    }

    $mongoRoot = Join-Path $env:ProgramFiles "MongoDB\Server"
    if (Test-Path $mongoRoot) {
        $mongod = Get-ChildItem -Path $mongoRoot -Filter "mongod.exe" -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1

        if ($mongod) {
            return $mongod.FullName
        }
    }

    return $null
}

function Get-MongoInfo {
    $mongodPath = Find-MongoExecutable

    if ($mongodPath) {
        try {
            $versionOutput = & $mongodPath --version 2>&1
            $versionLine = $versionOutput | Select-String "db version" | Select-Object -First 1
            $version = if ($versionLine) { $versionLine.Line.Trim() } else { ($versionOutput | Select-Object -First 1).ToString() }

            return @{
                Installed = $true
                Command   = $mongodPath
                Version   = $version
            }
        } catch {}
    }

    $service = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
    if ($service) {
        return @{
            Installed = $true
            Command   = $null
            Version   = "Installed - MongoDB Windows service detected"
        }
    }

    return @{ Installed = $false; Command = $null; Version = $null }
}

function Install-WingetPackage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PackageId,

        [Parameter(Mandatory = $true)]
        [string]$DisplayName
    )

    Write-Host ""
    Write-Host "Installing latest available $DisplayName..." -ForegroundColor Yellow

    $arguments = @(
        "install",
        "--id", $PackageId,
        "--exact",
        "--source", "winget",
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
        "--disable-interactivity"
    )

    $process = Start-Process `
        -FilePath "winget.exe" `
        -ArgumentList $arguments `
        -Wait `
        -PassThru `
        -NoNewWindow

    if ($process.ExitCode -ne 0) {
        Write-Host ""
        Write-Host "ERROR: $DisplayName installation failed." -ForegroundColor Red
        Write-Host "winget exit code: $($process.ExitCode)" -ForegroundColor Red
        return $false
    }

    Refresh-EnvironmentPath

    Write-Host "$DisplayName installer completed." -ForegroundColor Green
    return $true
}

function Install-Python {
    # winget resolves the latest release available for this maintained Python branch.
    # Update this ID when moving the application to a newer supported Python branch.
    $success = Install-WingetPackage -PackageId "Python.Python.3.13" -DisplayName "Python"
    if (-not $success) { return $false }

    Write-Host "Waiting for Python installation to become available..." -ForegroundColor Yellow
    for ($i = 0; $i -lt 15; $i++) {
        Refresh-EnvironmentPath
        $python = Get-PythonInfo
        if ($python.Installed) {
            Write-Host "[OK] Python verified: $($python.Version)" -ForegroundColor Green
            Write-Host "     $($python.Command)" -ForegroundColor DarkGray
            return $true
        }
        Start-Sleep -Seconds 2
    }

    Write-Host "ERROR: Python installation completed but verification failed." -ForegroundColor Red
    return $false
}

function Install-MongoDB {
    $success = Install-WingetPackage -PackageId "MongoDB.Server" -DisplayName "MongoDB Community Server"
    if (-not $success) { return $false }

    Write-Host "Waiting for MongoDB installation to become available..." -ForegroundColor Yellow
    for ($i = 0; $i -lt 15; $i++) {
        Refresh-EnvironmentPath
        $mongo = Get-MongoInfo
        if ($mongo.Installed) {
            Write-Host "[OK] MongoDB verified: $($mongo.Version)" -ForegroundColor Green
            if ($mongo.Command) {
                Write-Host "     $($mongo.Command)" -ForegroundColor DarkGray
            }

            $service = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
            if ($service -and $service.Status -ne "Running") {
                Write-Host "Starting MongoDB service..." -ForegroundColor Yellow
                try {
                    Start-Service -Name "MongoDB"
                    $service.WaitForStatus(
                        [System.ServiceProcess.ServiceControllerStatus]::Running,
                        [TimeSpan]::FromSeconds(30)
                    )
                    Write-Host "[OK] MongoDB service is running." -ForegroundColor Green
                } catch {
                    Write-Host "WARNING: MongoDB is installed but its service could not be started." -ForegroundColor Yellow
                    Write-Host $_.Exception.Message -ForegroundColor Yellow
                }
            } elseif ($service) {
                Write-Host "[OK] MongoDB service is running." -ForegroundColor Green
            }

            return $true
        }
        Start-Sleep -Seconds 2
    }

    Write-Host "ERROR: MongoDB installation completed but verification failed." -ForegroundColor Red
    return $false
}

# Check prerequisites and installed software.
Test-Winget
Refresh-EnvironmentPath

Write-Host ""
Write-Host "Checking installed components..." -ForegroundColor Cyan

$pythonInfo = Get-PythonInfo
$mongoInfo = Get-MongoInfo

Write-Host ""
if ($pythonInfo.Installed) {
    Write-Host "[OK] Python installed" -ForegroundColor Green
    Write-Host "     $($pythonInfo.Version)"
    Write-Host "     $($pythonInfo.Command)" -ForegroundColor DarkGray
} else {
    Write-Host "[MISSING] Python is not installed." -ForegroundColor Yellow
}

Write-Host ""
if ($mongoInfo.Installed) {
    Write-Host "[OK] MongoDB installed" -ForegroundColor Green
    Write-Host "     $($mongoInfo.Version)"
    if ($mongoInfo.Command) {
        Write-Host "     $($mongoInfo.Command)" -ForegroundColor DarkGray
    }
} else {
    Write-Host "[MISSING] MongoDB Community Server is not installed." -ForegroundColor Yellow
}

$pythonMissing = -not $pythonInfo.Installed
$mongoMissing = -not $mongoInfo.Installed
$installPython = $false
$installMongo = $false

if ($Unattended) {
    $installPython = $pythonMissing
    $installMongo = $mongoMissing
    $generateDemo = $true
} else {
    Write-Host ""
    if (-not $pythonMissing -and -not $mongoMissing) {
        Write-Host "Python and MongoDB are already installed." -ForegroundColor Green
        Write-Host ""
    }
    Write-Host "Select actions to perform:" -ForegroundColor Cyan
    Write-Host "  1 - Python"
    Write-Host "  2 - MongoDB Community Server"
    Write-Host "  3 - Generate Demo Data"
    Write-Host "  0 - All missing components with demo data"
    Write-Host "  Q - Skip installation"
    Write-Host ""

    while ($true) {
        $selection = (Read-Host "Enter selection").Trim().ToUpper()

        switch ($selection) {
            "1" {
                if ($pythonMissing) { $installPython = $true }
                else { Write-Host "Python is already installed." -ForegroundColor Green }
                break
            }
            "2" {
                if ($mongoMissing) { $installMongo = $true }
                else { Write-Host "MongoDB is already installed." -ForegroundColor Green }
                break
            }
	    "3" {
		Write-Host "Generating Demo data selected."
		$generateDemo = $true
		break
	    }
            "0" {
                $installPython = $pythonMissing
                $installMongo = $mongoMissing
                $generateDemo = $true
                break
            }
            "Q" {
                Write-Host "Installation skipped by user." -ForegroundColor Cyan
                break
            }
            default {
                Write-Host "Invalid selection. Enter 0, 1, 2 or Q." -ForegroundColor Red
                continue
            }
        }
        break
    }
}

if ($installPython) {
    if (-not (Install-Python)) { exit 1 }
}

if ($installMongo) {
    if (-not (Install-MongoDB)) { exit 1 }
}

# Final verification.
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Final Environment Verification" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Refresh-EnvironmentPath
$pythonInfo = Get-PythonInfo
$mongoInfo = Get-MongoInfo

Write-Host ""
if ($pythonInfo.Installed) {
    Write-Host "[OK] Python: $($pythonInfo.Version)" -ForegroundColor Green
} else {
    Write-Host "[NOT INSTALLED] Python" -ForegroundColor Yellow
}

if ($mongoInfo.Installed) {
    Write-Host "[OK] MongoDB: $($mongoInfo.Version)" -ForegroundColor Green
} else {
    Write-Host "[NOT INSTALLED] MongoDB" -ForegroundColor Yellow
}

# Install application Python dependencies.
if ($pythonInfo.Installed) {
    $reqFile = Join-Path $PSScriptRoot "requirements.txt"
    if (Test-Path $reqFile) {
        Write-Host ""
        Write-Host "Installing Python requirements..." -ForegroundColor Yellow

        & $pythonInfo.Command -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) {
            Write-Host "WARNING: pip upgrade failed; continuing with requirements installation." -ForegroundColor Yellow
        }

        & $pythonInfo.Command -m pip install -r $reqFile
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Python requirements installation failed." -ForegroundColor Red
            exit 1
        }

        Write-Host "[OK] Python requirements installed successfully." -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "WARNING: requirements.txt was not found. Skipping dependency installation." -ForegroundColor Yellow
    }
}

if ($generateDemo) {
    if ($pythonInfo.Installed) {
        $demoScript = Join-Path $PSScriptRoot "setup_environment.py"
        Write-Host ""
        Write-Host "Generating Demo data..." -ForegroundColor Yellow
        & $pythonInfo.Command $demoScript
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to generate demo data." -ForegroundColor Red
            exit 1
        } else {
            Write-Host "[OK] Demo data generated successfully." -ForegroundColor Green
        }
    } else {
        Write-Host "WARNING: Python is not installed. Cannot generate demo data." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "The database will initialize automatically with default roles"
Write-Host "and the 'admin' user on first startup."
Write-Host ""
Write-Host "To start the application, run:"
Write-Host "    .\start.bat" -ForegroundColor Cyan
Write-Host ""
