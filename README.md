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
