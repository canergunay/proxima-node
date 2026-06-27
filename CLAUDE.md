# Proxima Node (ADM) — Claude Code Project Instructions

## What is Proxima Node?

Centralized infrastructure management (ADM) for Proxima VPN exit nodes and DPI bypass nodes.
Manages server provisioning via Ansible, monitoring, alerting, and VPN server federation.

---

## CRITICAL: Deployment Discipline

**Git is the single source of truth. No exceptions.**

1. **ALL changes go through git** — code is written locally, committed, pushed, then deployed
2. **NEVER apply changes directly on production servers** — no `vim`, no `sed`, no manual edits
3. **NEVER leave uncommitted changes on the server** — if hotfixes are absolutely necessary, they MUST be immediately backported to the local codebase and committed
4. **Deploy flow is ALWAYS:** local edit → commit → push → SSH pull → restart
5. **Before deploying:** verify `git status` on the server shows clean working tree
6. **After deploying:** verify `git log -1` on the server matches the pushed commit

**This rule was violated in the past** (backend VPN metrics code was applied directly on the server without committing to git). This caused code drift between the repository and production. **This must never happen again.**

---

## Language & i18n Rules

- **UI language:** English is the primary and default language
- **i18n support:** Turkish (`tr`) and Russian (`ru`) must be supported
- **New UI string:** add key to ALL THREE locale files before committing
- **Default locale:** `en`

---

## Commit Guidelines

- Do NOT include `Co-Authored-By` lines
- Do NOT include Claude's name in commits
- Keep the `Generated with Claude Code` footer

---

## Tech Stack

### Backend (ADM)
- Python 3.12, Flask
- SQLite database
- Ansible for server provisioning
- JWT authentication, bcrypt password hashing
- Background scheduler for monitoring

### Frontend (ADM)
- React 19 + Vite 6
- MUI v6 (Material UI) — dark theme
- TypeScript
- i18next for internationalization
- recharts for monitoring charts
- Built output served by Flask from `backend/static/`

### Infrastructure Management
- Ansible playbooks for server provisioning
- SSH key-based authentication to managed servers
- proxima-agent on each managed server (HTTPS API on port 5051)

---

## Project Structure

```
proxima-node/
├── adm/
│   ├── backend/          # Flask Python application
│   │   ├── app.py        # Entry point
│   │   ├── api/          # API blueprints
│   │   ├── core/         # Config, DB, auth, scheduler
│   │   ├── data/         # Runtime data (gitignored)
│   │   └── static/       # Built frontend (generated, gitignored)
│   ├── frontend/         # React + TypeScript
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   ├── components/
│   │   │   ├── api/
│   │   │   └── locales/  # en.json, tr.json, ru.json
│   │   ├── public/       # Static assets (favicon, PWA icons, robots.txt)
│   │   ├── package.json
│   │   └── vite.config.ts
│   ├── adm.service       # Systemd service file
│   └── Makefile          # Build & install commands
├── inventory/
│   ├── hosts.yml         # Ansible inventory
│   ├── group_vars/       # Shared Ansible variables
│   └── host_vars/        # Per-server secrets (gitignored)
├── playbooks/            # Ansible playbooks
├── roles/                # Ansible roles
└── ansible.cfg
```

---

## Deployment

### Server Details

| Server | SSH alias | Path | Service |
|--------|-----------|------|---------|
| ERG | `erg` | `/opt/erg/proxima-node` | `proxima-adm.service` (port 5002) |

### Deploy Command

Node.js is NOT installed on the server. Frontend is built locally, then copied via scp.

```bash
# 1. Build frontend locally
cd adm/frontend && npm run build

# 2. Push code to GitHub
git add . && git commit && git push

# 3. Copy built frontend to server
scp -r adm/backend/static/ erg:/tmp/adm-static/

# 4. Deploy on server
ssh erg "cd /opt/erg/proxima-node && sudo git pull && sudo rm -rf adm/backend/static && sudo mv /tmp/adm-static adm/backend/static && sudo systemctl restart proxima-adm.service"
```

### Pre-deploy Checklist

1. All changes committed locally
2. Frontend build succeeds locally (`cd adm/frontend && npm run build`)
3. `git push` completed
4. Server has clean working tree (`git status` shows no changes)

---

## SEO/Crawling Policy

All Proxima-related sites are private. No search engine indexing, no AI bot access.
- `robots.txt` blocks all crawlers
- Meta tags in `index.html` block indexing
- This applies to adm.prxa.net and all connected services

---

## SSH Policy

**Claude Code MUST explicitly ask for user confirmation before using any SSH connection.**
