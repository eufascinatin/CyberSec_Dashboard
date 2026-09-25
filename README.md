# CyberSec Dashboard

A real-time cybersecurity telemetry dashboard and incident simulator. This package is the ready-to-deploy build: a **Streamlit** web UI, a background engine that simulates sensor telemetry and detects incidents, **SQLite** for configuration/RBAC and **MongoDB** for telemetry and audit data.

---


## Requirements

| Component | Notes |
|-----------|-------|
| Windows 10/11 | Launchers and installer are `.bat` / PowerShell. `winget` (App Installer) is needed for automatic installation. |
| Python 3 | Installed automatically as Python 3.13 (`Python.Python.3.13`) if missing. |
| MongoDB Community Server | Installed automatically (`MongoDB.Server`) if missing; expected at `mongodb://localhost:27017/`. |
| Python packages | `streamlit>=1.34.0`, `streamlit-option-menu`, `streamlit-cookies-controller`, `pymongo`, `sqlalchemy`, `pandas`, `plotly`, `pytz`, `python-dateutil` |

## Installation

Double-click **`install.bat`** (or run it from a terminal). It launches `setup\setup.ps1`, which:

1. Verifies `winget` is available.
2. Detects Python and MongoDB and shows what is missing.
3. Shows a menu (interactive mode):
   - `1` – install Python
   - `2` – install MongoDB Community Server (and start its service)
   - `3` – generate demo data
   - `0` – install all missing components **and** generate demo data
   - `Q` – skip
4. Installs `setup\requirements.txt` with pip.
5. If demo data was selected, runs `setup\setup_environment.py`.

For a non-interactive install that installs anything missing and generates demo data:

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -File setup\setup.ps1 -Unattended
```


## Running

```bat
start.bat        :: or  .\start.ps1
```

This opens the **Engine Runner** in a new window and starts the dashboard at **http://localhost:4513**.

To run the parts separately:

```bash
python engine_runner.py
streamlit run main.py --server.address localhost --server.port 4513
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `winget` not found | Install or update *App Installer* from the Microsoft Store, then run `install.bat` again. |
| Installer says validation failed | Make sure MongoDB is running (`MongoDB` service) and re-run. Setup files are kept in that case. |
| `No active servers found. Exiting.` | `admin_config.db` has no active servers – run demo-data setup or activate one in Settings → Servers, then restart the engine. |
| `Failed to connect to MongoDB` | Start the MongoDB service or correct the server URI in Settings → Servers. |
| `No online sensors found assigned to <db>` | Assign sensors to the server in Settings → Sensors. |
| Dashboard empty | The engine is not running, or the server is inactive/offline. |
| `setup\` folder is gone and you need to re-run setup | The installer removes it after success. Restore it from the original package. |
