# systemd deployment

Example `/etc/systemd/system/nmi-energy-calculator.service`:

```ini
[Unit]
Description=NMI Energy Plan Calculator
After=network.target

[Service]
Type=simple
User=nmi-calculator
Group=nmi-calculator
WorkingDirectory=/opt/nmi-energy-calculator
ExecStart=/opt/nmi-energy-calculator/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/nmi-energy-calculator

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nmi-energy-calculator
sudo systemctl status nmi-energy-calculator
```

Put a reverse proxy and HTTPS/authentication in front of the service if it is not restricted to a trusted LAN.
