# dynoip

**Dyno-IP Dynamic DNS client** — keep your hostname updated automatically from any Linux/macOS/Windows machine.

Zero dependencies. Pure Python stdlib.

## Install

```bash
pip install dynoip
```

## Usage

```bash
# Single update (auto-detect IP)
dynoip --token YOUR_TOKEN

# Set a specific IP
dynoip --token YOUR_TOKEN --ip 203.0.113.50

# Run as a daemon (updates every 5 minutes)
dynoip --token YOUR_TOKEN --daemon

# Custom interval (every 2 minutes)
dynoip --token YOUR_TOKEN --daemon --interval 120

# Token via environment variable
export DYNOIP_TOKEN=your_token_here
dynoip
```

## As a systemd service

```ini
# /etc/systemd/system/dynoip.service
[Unit]
Description=Dyno-IP Dynamic DNS Updater
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=DYNOIP_TOKEN=your_token_here
ExecStart=/usr/local/bin/dynoip --daemon --interval 300
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now dynoip
```

## As a Python library

```python
from dynoip import update_ip, run_once

# Single update
result = update_ip("your_token")
print(result)
# {'success': True, 'status': 200, 'subdomain': 'myhost', 'new_ip': '203.0.113.7', 'changed': True}

# With logging
run_once("your_token")
```

## Links

- **Website**: https://dyno-ip.com
- **Dashboard**: https://dyno-ip.com/login
- **GitHub**: https://github.com/vehoelite/dyno-ip
