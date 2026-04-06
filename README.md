# Setup

## Create a virtual environment called "venv"
python3 -m venv venv

## Activate it 
### Windows
.\venv\Scripts\Activate.ps1  

### Linux/macOS
source venv/bin/activate

## Install required packages
pip install -r requirements.txt

# Script Usage

python main.py --video input/video1.mp4  

# Tauri Setup

Needed: cargo, python venv  
```
npm i && npm run tauri dev
```