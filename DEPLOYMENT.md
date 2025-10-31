# Deployment with Gunicorn and NGINX

This guide walks through deploying the TOEFL practice feedback service on a Linux server (Ubuntu/Debian style). Adjust paths and commands to suit your environment.

## Remark: Handling ports
sudo ss -lptn 'sport = :8000'
## 1. Server Preparation

1. SSH into the target machine (ensure DNS already points to the server).
2. Install prerequisites:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip nginx git
   ```
3. Create an application user and directory:
   ```bash
   sudo useradd -m -s /bin/bash aiuser || true
   sudo mkdir -p /opt/ai-toefl
   sudo chown -R aiuser:aiuser /opt/ai-toefl
   ```

## 2. Application Setup

1. Copy project files (`api.py`, `gemini_utils.py`, `frontend.html`, etc.) into `/opt/ai-toefl`.
2. Create and activate a virtual environment:
   ```bash
   cd /opt/ai-toefl
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install fastapi "uvicorn[standard]" gunicorn python-dotenv google-genai
   ```
4. Create `/etc/ai-toefl.env` to hold secrets:
   ```bash
   sudo bash -c 'cat > /etc/ai-toefl.env <<EOF
   GEMINI_API_KEY=REPLACE_ME
   PYTHONUNBUFFERED=1
   EOF'
   sudo chmod 600 /etc/ai-toefl.env
   ```

## 3. Gunicorn systemd Service

Create the service definition:

```bash
sudo bash -c 'cat > /etc/systemd/system/ai-toefl.service <<EOF
[Unit]
Description=AI TOEFL FastAPI (Gunicorn)
After=network.target

[Service]
User=aiuser
Group=aiuser
WorkingDirectory=/opt/ai-toefl
EnvironmentFile=/etc/ai-toefl/.env
ExecStart=/opt/ai-toefl/.venv/bin/gunicorn -k uvicorn.workers.UvicornWorker api:app \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --threads 2 \
  --timeout 120 \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile -
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF'
```

Reload systemd and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-toefl
sudo systemctl status ai-toefl
```

Logs are available with `sudo journalctl -u ai-toefl -f`.

## 4. NGINX Reverse Proxy

Copy the frontend HTML into a static location:

```bash
sudo mkdir -p /var/www/ai-toefl
sudo cp /opt/ai-toefl/frontend.html /var/www/ai-toefl/
sudo chown -R www-data:www-data /var/www/ai-toefl
```

Create an NGINX server block (replace `your.domain.com`):

```bash
sudo bash -c 'cat > /etc/nginx/sites-available/ai-toefl <<EOF
upstream ai_toefl_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name your.domain.com;
    client_max_body_size 25m;

    location /.well-known/acme-challenge/ { root /var/www/ai-toefl; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your.domain.com;

    ssl_certificate /etc/letsencrypt/live/your.domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your.domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 25m;

    root /var/www/ai-toefl;
    index frontend.html;

    location / {
        try_files $uri /frontend.html;
    }

    location /speaking-feedback {
        proxy_pass http://ai_toefl_backend/speaking-feedback;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_send_timeout 180s;
        proxy_read_timeout 180s;
    }

    location /writing-feedback {
        proxy_pass http://ai_toefl_backend/writing-feedback;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_send_timeout 180s;
        proxy_read_timeout 180s;
    }

    access_log /var/log/nginx/ai-toefl.access.log;
    error_log /var/log/nginx/ai-toefl.error.log warn;
}
EOF'
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/ai-toefl /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 5. TLS with Let’s Encrypt

Install Certbot plugins:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Obtain certificates:

```bash
sudo certbot --nginx -d your.domain.com
```

Certbot installs a timer for auto-renewal (`systemctl status certbot.timer`).

## 6. Post-Deployment Checks

1. Confirm Gunicorn health: `sudo systemctl status ai-toefl`.
2. Check ports: `ss -ltnp | grep 8000`.
3. Tail NGINX logs while testing:
   ```bash
   sudo tail -f /var/log/nginx/ai-toefl.access.log /var/log/nginx/ai-toefl.error.log
   ```
4. Browse to `https://your.domain.com/`, upload audio/text, and verify responses.

## 7. Updating the Application

1. Deploy new code to `/opt/ai-toefl`.
2. Reinstall Python deps if needed:
   ```bash
   source /opt/ai-toefl/.venv/bin/activate
   pip install -r requirements.txt  # if you create one
   ```
3. Copy updated `frontend.html` to `/var/www/ai-toefl/`.
4. Restart services:
   ```bash
   sudo systemctl restart ai-toefl
   sudo systemctl reload nginx
   ```

## 8. Troubleshooting

- **502 Bad Gateway**: Gunicorn not running or crashed. Check `journalctl -u ai-toefl`.
- **404 Not Found**: Confirm `frontend.html` exists under `/var/www/ai-toefl` and the NGINX site is enabled.
- **Large uploads rejected**: Increase `client_max_body_size` in NGINX and ensure FastAPI can handle the size.
- **Permission denied on static files**: Ensure `www-data` owns `/var/www/ai-toefl`.
- **Stale TLS certs**: Run `sudo certbot renew --dry-run` to validate automation.

With this setup, Gunicorn handles the FastAPI app, NGINX proxies requests and serves the React UI, and Let’s Encrypt provides automatic TLS management.
