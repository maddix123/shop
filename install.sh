#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_URL="https://github.com/your-org/shop-management-system.git"
APP_DIR="/opt/shop-management-system"
SERVICE_NAME="shop-management"

if [[ "${EUID}" -ne 0 ]]; then
  SUDO="sudo"
else
  SUDO=""
fi

CURRENT_USER="${SUDO_USER:-$(id -un)}"

read -r -p "GitHub repo URL [${DEFAULT_REPO_URL}]: " REPO_URL
REPO_URL="${REPO_URL:-$DEFAULT_REPO_URL}"

read -r -p "Port for web UI [8000]: " APP_PORT
APP_PORT="${APP_PORT:-8000}"

$SUDO apt-get update
$SUDO apt-get install -y git python3 python3-venv

if [[ -d "${APP_DIR}/.git" ]]; then
  $SUDO git -C "$APP_DIR" pull --ff-only
else
  $SUDO rm -rf "$APP_DIR"
  $SUDO git clone "$REPO_URL" "$APP_DIR"
fi

$SUDO chown -R "$CURRENT_USER":"$CURRENT_USER" "$APP_DIR"

$SUDO python3 -m venv "$APP_DIR/venv"
$SUDO "$APP_DIR/venv/bin/pip" install --upgrade pip
$SUDO "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

$SUDO tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=Shop Management System
After=network.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment=PORT=${APP_PORT}
ExecStart=${APP_DIR}/venv/bin/python ${APP_DIR}/app.py
Restart=always
User=${CURRENT_USER}

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload
$SUDO systemctl enable "${SERVICE_NAME}.service"
$SUDO systemctl restart "${SERVICE_NAME}.service"

echo "Installation complete."
echo "Open http://<your-server-ip>:${APP_PORT} to view the app."
