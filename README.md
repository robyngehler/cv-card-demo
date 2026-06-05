# CV Card Demo

This repository contains the CV Card Demo application for NVIDIA Jetson devices.

## Structure

- `app/` — Python application code
- `config/` — configuration files
- `scripts/` — startup and install scripts
- `systemd/` — systemd unit files for backend and kiosk services
- `docs/` — documentation
- `logs/` — application logs

## Quick start

1. Create the target directory and service user on the device.
2. Create a Python virtual environment and install dependencies from `requirements.txt`.
3. Copy `systemd/*.service` and `*.target` to `/etc/systemd/system/`.
4. Enable and start `cv-card-demo.target`.

Example:

```bash
cd /opt/cv-card-demo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo cp systemd/*.service systemd/*.target /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cv-card-demo.target
sudo systemctl start cv-card-demo.target
```
