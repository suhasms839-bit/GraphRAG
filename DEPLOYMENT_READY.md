# Deployment Ready: Manual Steps

## ✅ Completed

- [x] Timezone fixes: All `datetime.utcnow()` replaced with `datetime.now(timezone.utc)`
- [x] Production env values added to `.env`:
  - POSTGRES_PASSWORD
  - SECRET_KEY (strong 64-char random)
  - CORS_ORIGINS
  - DEBUG=False
- [x] Production Docker Compose overlay: `docker-compose.prod.yml`
- [x] Nginx API proxy config: `frontend/nginx.prod.conf`
- [x] Env template: `.env.production.example`

## ⚠️ Next Step: Install Docker

### Option 1: Docker Desktop (Recommended for Windows)
1. Download: https://www.docker.com/products/docker-desktop
2. Run installer (requires admin)
3. Complete setup wizard
4. Restart your machine
5. Open PowerShell and verify:
   ```powershell
   docker --version
   docker compose version
   ```

### Option 2: Docker Engine via WSL2 (Advanced)
1. Enable WSL2 on Windows
2. Install Docker inside WSL2
3. Configure Docker to run as daemon

## 🚀 After Docker is Installed

Run this command to deploy the production stack:

```powershell
cd c:\Users\HP\new\graphrag-learning-platform
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 📋 Important: Update These Values in `.env`

Before deploying, replace these placeholders with your actual values:

```
# YOUR DOMAIN
CORS_ORIGINS=https://your-domain.com,http://localhost:3000

# STRONG PASSWORD (change from current default)
POSTGRES_PASSWORD=SecureP@ssw0rd2024!GraphRAG

# Optional: Gmail OAuth (leave empty if not needed)
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_secret
GOOGLE_OAUTH_REDIRECT_URI=https://your-domain.com/api/mcp/auth/callback
```

## ✅ Deployment Health Checks

After `docker compose up -d`, verify:

```powershell
# Backend readiness (should return 200)
curl http://localhost/api/v1/health

# Full system status
curl http://localhost/health/readiness

# Frontend loads
curl http://localhost/
```

## 📦 Production Verification Checklist

- [ ] Docker Desktop installed and running
- [ ] `.env` updated with your actual domain/secrets
- [ ] `docker compose up -d --build` completes without errors
- [ ] All containers are healthy: `docker ps`
- [ ] Backend health check passes
- [ ] Frontend loads on http://localhost
- [ ] Can sign up and log in
- [ ] Can upload a test document
