# Shop Management System

Lightweight inventory management with a single-command Ubuntu installer script.

## Ubuntu VPS install (one script)

```bash
curl -fsSL https://raw.githubusercontent.com/your-org/shop-management-system/main/install.sh | bash
```

The installer will:

1. Ask for the GitHub repo URL (press Enter to accept the default).
2. Ask for the web UI port.
3. Install dependencies, set up a Python virtual environment, and configure a systemd service.

After installation, open:

```
http://<your-server-ip>:<port>
```

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
