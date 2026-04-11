# 🏰 Avalon Game - Production Deployment Guide

## Domain Setup
Single domain with path-based routing:
- **Frontend**: `avalon.weikit.me` → Port 3000
- **Backend**: `avalon.weikit.me/api/*` → Port 8001

## Backend CORS Configuration
```python
allow_origins=[
    "http://localhost:3000",
    "https://avalon.weikit.me",
]
```
Configurable via `CORS_ORIGINS` env var (comma-separated).

## 🚀 Quick Deploy Steps

```bash
# Using Docker
docker compose up --build -d
```

## 🔧 Cloudflare Tunnel Setup

```yaml
# cloudflared config.yml
tunnel: YOUR_TUNNEL_ID
credentials-file: /path/to/credentials.json

ingress:
  - hostname: avalon.weikit.me
    path: /api/*
    service: http://localhost:8001
  - hostname: avalon.weikit.me
    service: http://localhost:3000
  - service: http_status:404
```

## 🛠️ Troubleshooting

### If CORS errors persist:
1. Clear browser cache completely
2. Check browser console for exact error
3. Verify domains match exactly (no trailing slashes)
4. Ensure HTTPS is working

### If WebSocket connection fails:
1. Check that backend supports WebSocket upgrades
2. Verify Cloudflare has WebSocket support enabled
3. Check firewall allows port 8001

### Database connection issues:
1. Verify MongoDB is running: `sudo systemctl status mongod`
2. Check connection string in backend/.env
3. Restart services: `docker compose restart`

## 📊 Service Status Check
```bash
# Check Docker services
docker compose ps

# Check logs
docker compose logs -f backend
docker compose logs -f frontend

# Check ports
sudo netstat -tlnp | grep -E ':(3000|8001|27017)'
```
