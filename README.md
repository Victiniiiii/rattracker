# Create a virtual environment called "venv"
python3 -m venv venv

# Activate it (Linux/macOS)
source venv/bin/activate

# Activate it (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Now your shell should show (venv) at the start
pip install -r requirements.txt
python main.py

# Optional: Deactivate the virtual environment
deactivate

# Goal:
12266 pixels