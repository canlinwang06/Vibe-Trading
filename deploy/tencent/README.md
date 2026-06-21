# Tencent Cloud Three-Page Deployment

This package publishes only the read-only cloud display surface:

- `/vibe-trading/` for the React app.
- `/api/advisor/today-snapshot`
- `/api/advisor/stocks-snapshot`
- `/api/advisor/memory-snapshot`
- `/health`

The local workstation remains the full Vibe-Trading workbench. Codex continues
to run local inspection, analysis, data writes, and maintenance. The cloud
server is only a remote/mobile viewing window.

## Safety Boundaries

- Do not set `OPENAI_API_KEY` for this deployment.
- Do not store JoinQuant, broker, or exchange passwords on the cloud server.
- Do not expose Agent, Settings, upload, runtime, backtest, JoinQuant, or live
  trading endpoints through Nginx.
- Keep the backend bound to `127.0.0.1:8899`.
- Keep Nginx basic auth enabled by default.

## Build And Start

```bash
cd deploy/tencent
docker image inspect vibe-trading:cloud-three-page >/dev/null 2>&1 \
  && docker image tag vibe-trading:cloud-three-page vibe-trading:cloud-three-page-previous \
  || true
docker compose -f docker-compose.cloud.yml build
docker compose -f docker-compose.cloud.yml up -d
```

Install the Nginx allowlist file:

```bash
sudo cp nginx-vibe-trading.conf /etc/nginx/conf.d/vibe-trading.conf
sudo htpasswd -c /etc/nginx/.htpasswd-vibe-trading <user>
sudo nginx -t
sudo systemctl reload nginx
```

## Verification

```bash
curl -I http://127.0.0.1:8899/health
curl -I -u <user>:<password> http://127.0.0.1/vibe-trading/
curl -I -u <user>:<password> http://127.0.0.1/api/advisor/today-snapshot
curl -I -u <user>:<password> http://127.0.0.1/api/advisor/stocks-snapshot
curl -I -u <user>:<password> http://127.0.0.1/api/advisor/memory-snapshot
curl -I -u <user>:<password> http://127.0.0.1/api/advisor/transactions
curl -I -u <user>:<password> http://127.0.0.1/settings
curl -I -u <user>:<password> http://127.0.0.1/agent
```

Expected:

- `/vibe-trading/` returns the three-page app.
- The three snapshot APIs return `200` through Nginx after private access auth.
- `/health` returns healthy status.
- Old or sensitive endpoints return `404` through Nginx.

## Rollback

```bash
cd deploy/tencent
./rollback.sh
```

The rollback script expects `vibe-trading:cloud-three-page-previous` to exist.
Create that tag before publishing a new candidate.
