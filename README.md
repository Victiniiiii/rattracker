# Morris Water Maze Analysis

A video analysis tool for tracking rodent movement in Morris Water Maze experiments. Available as a standalone Python script or a compiled Tauri desktop application.

---

## Table of Contents

- [Requirements](#requirements)
- [Python Script - Manual Setup](#python-script--manual-setup)
  - [Windows](#windows-python)
  - [macOS](#macos-python)
  - [Linux](#linux-python)
  - [Script Usage](#script-usage)
- [Desktop App - Compile from Source](#desktop-app--compile-from-source)
  - [Automated (recommended)](#automated-recommended)
  - [Manual Compilation](#manual-compilation)
    - [Windows](#windows-compile)
    - [macOS](#macos-compile)
    - [Linux](#linux-compile)

---

## Requirements

| Tool | Version |
|---|---|
| Python | 3.12 |
| Node.js | 20.x |
| Rust / Cargo | latest stable |

---

## Python Script - Manual Setup

### Windows (Python) {#windows-python}

**1. Install Python 3.12**

Download and install from [python.org](https://www.python.org/downloads/). During installation, check **"Add Python to PATH"**.

**2. Create and activate a virtual environment**

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
```

> If you get an execution policy error, run this first:
> ```powershell
> Set-ExecutionPolicy Bypass -Scope Process
> ```

**3. Install dependencies**

```powershell
pip install -r requirements.txt
```

---

### macOS (Python) {#macos-python}

**1. Install Homebrew** (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**2. Install Python 3.12**

```bash
brew install python@3.12
```

**3. Create and activate a virtual environment**

```bash
python3.12 -m venv venv
source venv/bin/activate
```

**4. Install dependencies**

```bash
pip install -r requirements.txt
```

---

### Linux (Python) {#linux-python}

**1. Install system dependencies**

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

> If Python 3.12 is not available in your default repos:
> ```bash
> sudo apt install -y software-properties-common
> sudo add-apt-repository -y ppa:deadsnakes/ppa
> sudo apt update
> sudo apt install -y python3.12 python3.12-venv python3.12-dev
> ```

**2. Create and activate a virtual environment**

```bash
python3.12 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

---

### Script Usage

```
python main.py --video input/video1.mp4
```

Run `python main.py --help` for a full list of options.

---

## Desktop App - Compile from Source

### Automated (recommended)

The automated scripts install all required tools from scratch (Python, Node.js, Rust, system libraries), compile the Python sidecar with Nuitka, and build the Tauri app.

**Windows**

```powershell
Set-ExecutionPolicy Bypass -Scope Process
.\compile_windows.ps1
```

**macOS** - auto-detects Intel vs Apple Silicon

```bash
chmod +x compile_mac.sh
./compile_mac.sh
```

**Linux**

```bash
chmod +x compile_linux.sh
./compile_linux.sh
```

---

### Manual Compilation

If you prefer to run each step yourself, follow the platform-specific instructions below.

---

#### Windows (Compile) {#windows-compile}

**1. Install required tools**

- [Node.js 20 LTS](https://nodejs.org/)
- [Python 3.12](https://www.python.org/downloads/)
- [Rust](https://rustup.rs/) - after installing, run:
  ```powershell
  rustup install stable
  rustup default stable
  ```
- [Visual Studio 2022 Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) - select the **"Desktop development with C++"** workload

**2. Set up Python virtual environment**

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install nuitka
```

**3. Install Tauri CLI and frontend dependencies**

```powershell
cargo install tauri-cli --locked
npm install
```

**4. Compile Python sidecar**

```powershell
.\venv\Scripts\python.exe -m nuitka --standalone --onefile --include-package=cv2 --output-filename=main.exe main.py
mkdir -p src-tauri\bin
move main.exe src-tauri\bin\main-x86_64-pc-windows-msvc.exe
```

**5. Build the Tauri app**

```powershell
npm run tauri build
```

---

#### macOS (Compile) {#macos-compile}

**1. Install Homebrew** (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**2. Install required tools**

```bash
brew install node@20 python@3.12
brew link node@20 --force
brew link python@3.12 --force
```

Install Rust:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
```

Add the target for your machine:

```bash
# Apple Silicon (M1/M2/M3/M4)
rustup target add aarch64-apple-darwin

# Intel
rustup target add x86_64-apple-darwin
```

**3. Set up Python virtual environment**

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install nuitka
```

**4. Install Tauri CLI and frontend dependencies**

```bash
cargo install tauri-cli --locked
npm install
```

**5. Compile Python sidecar**

```bash
# Detect your arch
ARCH="$(uname -m)"
TARGET_TRIPLE="x86_64-apple-darwin"
[ "$ARCH" = "arm64" ] && TARGET_TRIPLE="aarch64-apple-darwin"

python -m nuitka --standalone --onefile --include-package=cv2 --macos-target-arch="$ARCH" main.py

mkdir -p src-tauri/bin
mv main src-tauri/bin/main-${TARGET_TRIPLE}
chmod +x src-tauri/bin/main-${TARGET_TRIPLE}
```

**6. Build the Tauri app**

```bash
npm run tauri build
```

---

#### Linux (Compile) {#linux-compile}

**1. Install system dependencies**

```bash
sudo apt update
sudo apt install -y \
    curl wget file build-essential pkg-config patchelf \
    libwebkit2gtk-4.1-dev libssl-dev libayatana-appindicator3-dev \
    librsvg2-dev libxdo-dev \
    python3.12 python3.12-venv python3.12-dev
```

**2. Install Node.js 20**

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**3. Install Rust**

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
```

**4. Set up Python virtual environment**

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install nuitka
```

**5. Install Tauri CLI and frontend dependencies**

```bash
cargo install tauri-cli --locked
npm install
```

**6. Compile Python sidecar**

```bash
python -m nuitka --standalone --onefile --include-package=cv2 main.py
mkdir -p src-tauri/bin
mv main.bin src-tauri/bin/main-x86_64-unknown-linux-gnu 2>/dev/null || \
mv main     src-tauri/bin/main-x86_64-unknown-linux-gnu
chmod +x src-tauri/bin/main-x86_64-unknown-linux-gnu
```

**7. Build the Tauri app**

```bash
npm run tauri build
```