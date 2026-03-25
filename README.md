<p align="center">
  <img src="media/globe_only.png" alt="Dyno-IP" width="80" />
</p>

<h1 align="center">Dyno-IP</h1>

<p align="center">
  <strong>Dynamic DNS & Secure Tunnels — No Router Config Required</strong>
</p>

<p align="center">
  <a href="https://dyno-ip.com">Website</a> •
  <a href="https://dyno-ip.com/login">Dashboard</a> •
  <a href="#download">Download</a> •
  <a href="#pricing">Pricing</a>
</p>

---

## What is Dyno-IP?

Dyno-IP lets you **host services from any internet connection** without touching your router.

- **Dynamic DNS** — Your subdomain always points to your current IP, even on residential or mobile connections.
- **Secure Tunnels** — Expose local HTTP, HTTPS, TCP, and UDP services to the internet through encrypted tunnels.
- **Zero port forwarding** — Tunnels bypass NAT and firewalls completely. No UPnP, no DMZ, no router login.

### Use Cases

| Use case | How |
|---|---|
| **Host a website** | Create a tunnel → point your subdomain → your local web server is live |
| **Game server** | Create a TCP/UDP tunnel → share the hostname → friends connect directly |
| **Home lab** | Access self-hosted services (Plex, Home Assistant, NAS) from anywhere |
| **Development** | Share localhost with teammates or webhook providers |
| **API backend** | Run a FastAPI/Express server at home, expose it with a real hostname |
| **Security cameras** | Access your DVR/NVR remotely without exposing ports |

---

## Download

### Windows (recommended)

Download the latest **[DynoIP-Setup.exe](https://github.com/vehoelite/dyno-ip/releases/download/v1.0.0/DynoIP-Setup.exe)**.

The installer includes:
- **DynoIP Desktop App** — GUI dashboard with login, subdomain management, tunnel control, and activity monitoring
- **DynoIP Background Service** (optional) — Keeps your IP updated automatically, even when the app is closed

### Linux

```bash
# Debian/Ubuntu
sudo dpkg -i dynoip_1.0.0_all.deb
sudo systemctl enable --now dynoip.timer

# Or use the standalone script
curl -s https://dyno-ip.com/api/ip/SUBDOMAIN/update \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Any Platform (API)

```bash
# Update your IP with a single cURL request
curl -X POST https://dyno-ip.com/api/ip/SUBDOMAIN/update \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Features

| Feature | Description |
|---|---|
| **Dynamic DNS** | Automatic IP updates via Cloudflare DNS across 10+ domains |
| **Secure Tunnels** | HTTP, HTTPS, TCP, and UDP — encrypted end-to-end |
| **10+ Domains** | .com, .info, .store, .online, .site, .cloud, and more |
| **Full DNS Management** | A, AAAA, CNAME, MX, TXT records with Cloudflare proxy toggle |
| **Activity Feed** | Real-time log of IP changes, traffic, tunnel events, and logins |
| **Traffic Analytics** | HTTP request counts, unique visitors, bandwidth per subdomain |
| **2FA Security** | TOTP-based two-factor authentication for your account |
| **OAuth Login** | Sign in with Google or GitHub |
| **Cross-Platform** | Windows app, Linux daemon, web dashboard, REST API |
| **Session Log** | Local event log in the desktop app for troubleshooting |

---

## Pricing

Start free. Upgrade when you need more.

| | **Free** | **Pro** — $4.99/mo | **Business** — $9.99/mo |
|---|:---:|:---:|:---:|
| Subdomains | 1 | 5 | Unlimited |
| Tunnels | 1 | 5 | Unlimited |
| Bandwidth | 10 GB/mo | 100 GB/mo | Unlimited |
| Connections | 5 simultaneous | 50 | Unlimited |
| Analytics | 24 hours | 7-day history | 30-day + export |
| Custom domains | — | ✓ | ✓ |
| Priority DNS | — | ✓ | ✓ |
| Priority support | — | — | ✓ |

> **No speed limits on any tier.** Every user gets full-speed tunnels. Limits are on quantity and monthly bandwidth, not throughput.

---

## Architecture

```
┌─────────────────────────────────┐
│        Cloudflare DNS           │  ← DNS records for all domains
│    dyno-ip.com, *.dyno-ip.com  │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│       Dyno-IP Backend           │  ← FastAPI (Python)
│       (API + Dashboard)         │     JWT auth, 2FA, OAuth
│       Port 8500                 │     Cloudflare integration
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│       Pangolin Tunnel Server    │  ← Tunnel orchestration
│       (HTTP/HTTPS/TCP/UDP)      │     Newt agents connect here
│       WireGuard + Traefik       │     Zero-config for end users
└─────────────────────────────────┘
```

- **Backend**: FastAPI on Python 3.12+, MariaDB, JWT + bcrypt auth
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **DNS**: Cloudflare API (Global Key auth) for all DNS operations
- **Tunnels**: Pangolin + Newt (WireGuard-based) for encrypted tunnels
- **Desktop Client**: Python + CustomTkinter, packaged with PyInstaller
- **Analytics**: Cloudflare Analytics API (GraphQL + REST) polled server-side

--- 

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy, MariaDB |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| DNS | Cloudflare API |
| Tunnels | Pangolin, Newt, WireGuard, Traefik |
| Desktop | Python, CustomTkinter, PyInstaller |
| Auth | JWT, bcrypt, TOTP 2FA, Google/GitHub OAuth |
| Analytics | Cloudflare GraphQL + REST APIs |

---

## Coming Soon
Much more control is coming to your tunnels and subdomain
1. Link Sharing, single links that can re-direct users to your service.
2. QRcode service linking.
3. Service permissions, allow only certain email address, user agent, IP, geographical location and many more!
4. Approval requests, allow someone to send notification in real-time for approval to your service.
5. Setup identity providers: OAuth2/OIDC, Google, Github etc.
6. Send invitations for someone to access your service.
7. Setup multiple services to one location.
8. Setup ZeroTrust private access.
9. SMS and call validation services.

## License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built by <a href="https://dyno-ip.com">Novamind Labs</a></sub>
</p>
