# Deploying Mine Rescue Center

A step-by-step runbook for publishing the site on a small VPS.

## Architecture

```
        Internet (HTTPS)
              │
          ┌───▼───┐   automatic Let's Encrypt cert
          │ Caddy │   serves /media/* off disk; proxies the rest
          └───┬───┘
              │ HTTP 127.0.0.1:8001
        ┌─────▼─────┐
        │ gunicorn  │  Django app (WhiteNoise serves /static/*)
        └─────┬─────┘
              │
     SQLite (db.sqlite3) + media/ on the server's persistent disk
```

- **Database:** SQLite, a single file on disk. Fine for this read-heavy site.
- **Content:** shipped as the `pages/fixtures/pages_data.json` fixture and loaded
  with `loaddata` (the DB itself is never committed).
- **Media (problem PDFs):** uploaded from your machine. They **cannot** be
  regenerated on the server — the `.docx`/`.ppt`→PDF step needs Windows + Office —
  so the converted PDFs in `media/` are the source of truth and must be copied up.

## You provide

1. A **domain** (e.g. from Namecheap/Cloudflare/Porkbun, ~$10–15/yr).
2. A **VPS**: any provider's smallest tier is plenty (1 vCPU / 1 GB RAM).
   Recommended image: **Ubuntu 24.04 LTS**. (Hetzner CX22, DigitalOcean
   $6 droplet, Linode Nanode, etc.)

Throughout, replace `yourdomain.com` and `SERVER_IP` with your real values.

---

## 1. Create the VPS

Create an Ubuntu 24.04 server and add your SSH key during creation. Note its
public IP (`SERVER_IP`).

## 2. Point DNS at it

At your domain registrar, create two DNS **A records**:

| Type | Name  | Value       |
|------|-------|-------------|
| A    | `@`   | `SERVER_IP` |
| A    | `www` | `SERVER_IP` |

DNS can take a few minutes to an hour to propagate. Caddy needs this working to
issue the HTTPS certificate (step 11).

## 3. First login, base packages, app user

```bash
ssh root@SERVER_IP

# Base packages
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git rsync ufw

# Firewall: allow SSH + web
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable

# Dedicated unprivileged user to run the app
adduser --disabled-password --gecos "" mine
install -d -o mine -g mine /srv/mine-rescue
```

Install Caddy (official repo):

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy
```

## 4. Get the code

```bash
su - mine
git clone https://github.com/jakeolson657/Mine_Rescue_Center.git /srv/mine-rescue
cd /srv/mine-rescue
```

## 5. Python environment

```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

## 6. Environment file (secrets)

```bash
cp deploy/mine-rescue.env.example .env
nano .env
```

Set a real `DJANGO_SECRET_KEY` (generate one with the command in the file's
comment), your domain in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`,
and keep `DJANGO_DEBUG=False`. Lock it down: `chmod 600 .env`.

## 7. Database + content

```bash
set -a; . ./.env; set +a          # load env into this shell

./venv/bin/python manage.py migrate
./venv/bin/python manage.py loaddata pages/fixtures/pages_data.json
./venv/bin/python manage.py createsuperuser   # your admin login (not in the fixture)
```

## 8. Static files

```bash
./venv/bin/python manage.py collectstatic --noinput
```

## 9. Media files (upload from your Windows machine)

The `media/` folder (the problem PDFs, ~1+ GB) is gitignored, so it isn't in the
repo. Copy it up **from your local machine**. Easiest on Windows is the
**WinSCP** GUI (drag `media/` into `/srv/mine-rescue/`). CLI equivalent from the
project folder in Git Bash / PowerShell:

```bash
rsync -avz --progress media/ mine@SERVER_IP:/srv/mine-rescue/media/
# (or, if rsync isn't available: scp -r media mine@SERVER_IP:/srv/mine-rescue/)
```

Then make sure the app user owns them: on the server, `chown -R mine:mine /srv/mine-rescue/media`.

## 10. Run the app (systemd)

```bash
# as root:
cp /srv/mine-rescue/deploy/gunicorn.service /etc/systemd/system/mine-rescue.service
systemctl daemon-reload
systemctl enable --now mine-rescue
systemctl status mine-rescue        # should be "active (running)"
```

## 11. Caddy (HTTPS)

Edit `/srv/mine-rescue/deploy/Caddyfile`, replace `yourdomain.com` (both places),
then:

```bash
cp /srv/mine-rescue/deploy/Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy
journalctl -u caddy -f   # watch it obtain the certificate
```

## 12. Verify

Visit `https://yourdomain.com` — landing page, calendar, and `/problems/` should
all load, PDFs should preview, and `/admin/` should log in with your superuser.

---

## Updating the site later

**Code/template changes:**
```bash
ssh mine@SERVER_IP
cd /srv/mine-rescue && git pull
./venv/bin/pip install -r requirements.txt        # if deps changed
./venv/bin/python manage.py migrate               # if models changed
./venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart mine-rescue
```

**Content changes** are easiest made directly in the live admin
(`https://yourdomain.com/admin/`). If instead you edit content locally and want
to push it up, re-export the fixture locally and reload it on the server:
```bash
# local (Windows):  PYTHONUTF8=1 python manage.py dumpdata pages --indent 2 -o pages/fixtures/pages_data.json
# commit + push, then on the server: git pull && ./venv/bin/python manage.py loaddata pages/fixtures/pages_data.json
```
New media added locally must be re-uploaded (step 9). Beware: `loaddata` of the
`pages` app overwrites those rows with the fixture's version, so pick **one**
place (server admin **or** local) as your source of truth for content.
