# Setup

## All required packages (Linux/Ubuntu)

Needed: cargo 1.94.0, Python 3.12.3 (with venv), Node.js v20.20.2

```
sudo apt install \
    patchelf \
    libglib2.0-dev \
    libgtk-3-dev \
    libwebkit2gtk-4.1-dev \
    build-essential \
    pkg-config \
    libssl-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev \
    libxdo-dev \ 
    python3.12-dev
```

## Create a virtual environment called "venv"

```
python3 -m venv venv
```

## Activate it
### Windows

```
.\venv\Scripts\Activate.ps1
```

### Linux/macOS

```
source venv/bin/activate
```

## Install required Python packages

```
pip install -r requirements.txt
```

# Script Usage

```
python main.py --video input/video1.mp4
```

# Tauri Setup

```
npm i && npm run tauri dev
```

## Compile Python using Nuitka

```
python -m nuitka --standalone --onefile --include-package=cv2 main.py && mv main.bin src-tauri/bin/main-x86_64-unknown-linux-gnu
```

## Run auto-compiler scripts

### Windows:
```
Set-ExecutionPolicy Bypass -Scope Process
```
```
.\compile_windows.ps1
```
### Linux: 
```
chmod +x compile_linux.sh
```
```
./compile_linux.sh
```