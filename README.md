# Setup

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

## Install required packages

```
pip install -r requirements.txt
```

# Script Usage

```
python main.py --video input/video1.mp4
```

# Tauri Setup

Needed: cargo 1.94.0, Python 3.12.3 (with venv), Node.js v20.20.2

```
npm i && npm run tauri dev
```

## Compile Python using Nuitka

```
python -m nuitka --standalone --onefile --include-package=cv2 main.py
```

FATAL: Error, standalone mode on Linux requires 'patchelf' to be installed. Use 'apt/dnf/yum install patchelf' first.
sudo apt install patchelf
sudo dnf install patchelf
sudo yum install patchelf
sudo pacman -S patchelf
Unknown package manager. Install patchelf manually.