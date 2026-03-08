#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/picoclaw-rp2040"
SERVICE_NAME="robot-agent.service"
USER_NAME="${SUDO_USER:-$USER}"

sudo apt update
sudo apt install -y git rsync python3 python3-pip python3-venv python3-serial avahi-daemon

sudo mkdir -p "$PROJECT_DIR"
sudo chown -R "$USER_NAME":"$USER_NAME" "$PROJECT_DIR"

if [ -f README.md ] && [ -d robot-agent ] && [ -d firmware-rp2040 ]; then
  rsync -av --delete --exclude '.venv/' --exclude '__pycache__/' --exclude 'logs/' ./ "$PROJECT_DIR"/
else
  echo "Run this script from the project root so it can copy files into $PROJECT_DIR"
  exit 1
fi

python3 -m venv "$PROJECT_DIR/.venv"
source "$PROJECT_DIR/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/robot-agent/requirements.txt"

TMP_SERVICE="$(mktemp)"
sed "s/^User=.*/User=$USER_NAME/" "$PROJECT_DIR/systemd/robot-agent.service" > "$TMP_SERVICE"
sudo cp "$TMP_SERVICE" "/etc/systemd/system/$SERVICE_NAME"
rm -f "$TMP_SERVICE"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo
echo "Bootstrap complete."
echo "Project deployed to: $PROJECT_DIR"
echo "Start service with: sudo systemctl start $SERVICE_NAME"
echo "Check logs with: sudo journalctl -u $SERVICE_NAME -f"
