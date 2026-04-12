$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonVersion = "3.12"
$SidecarName = "main"
$TargetTriple = "x86_64-pc-windows-msvc"
$SidecarDest = "src-tauri\bin\$SidecarName-$TargetTriple.exe"

Set-Location $ProjectRoot

function Command-Exists {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Install-Node {
    if (Command-Exists "node") {
        Write-Host "Node already installed: $(node -v)"
        return
    }

    winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
}

function Install-Rust {
    if (Command-Exists "cargo") {
        Write-Host "Rust already installed: $(cargo --version)"
        return
    }

    winget install Rustlang.Rustup --silent --accept-package-agreements --accept-source-agreements

    $env:Path += ";$env:USERPROFILE\.cargo\bin"
}

function Install-Python {
    if (Command-Exists "python") {
        $version = python --version
        if ($version -match "3\.12") {
            Write-Host "Python already installed: $version"
            return
        }
    }

    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
}

function Install-BuildTools {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"

    if (Test-Path $vswhere) {
        return
    }

    winget install Microsoft.VisualStudio.2022.BuildTools --silent --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools"
}

function Setup-Venv {
    if (!(Test-Path "venv")) {
        py -3.12 -m venv venv
    }

    & ".\venv\Scripts\python.exe" -m pip install --upgrade pip
    & ".\venv\Scripts\python.exe" -m pip install -r requirements.txt
    & ".\venv\Scripts\python.exe" -m pip install nuitka
}

function Install-TauriCli {
    cargo install tauri-cli --locked
}

function Install-FrontendDeps {
    npm install
}

function Build-PythonSidecar {
    & ".\venv\Scripts\python.exe" -m nuitka `
        --standalone `
        --onefile `
        --include-package=cv2 `
        --output-filename=main.exe `
        main.py

    New-Item -ItemType Directory -Force -Path "src-tauri\bin" | Out-Null

    if (Test-Path "main.exe") {
        Move-Item -Force "main.exe" $SidecarDest
    } else {
        throw "Python sidecar output not found"
    }
}

function Build-Tauri {
    npm run tauri build
}

Install-Node
Install-Rust
Install-Python
Install-BuildTools
Setup-Venv
Install-TauriCli
Install-FrontendDeps
Build-PythonSidecar
Build-Tauri

Write-Host "Windows build completed successfully"