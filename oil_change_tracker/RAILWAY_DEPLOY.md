# Railway Deployment Guide for Oil Change Tracker

## 🚀 Quick Deploy to Railway

### Step 1: Prepare Repository
```bash
# From your Codespace terminal:
cd /workspaces/ShopMasterOS
git add .
git commit -m "Add Railway deployment configuration"
git push origin main
```

### Step 2: Deploy on Railway
1. Visit: https://railway.app
2. Sign up with your GitHub account
3. Click "New Project" → "Deploy from GitHub repo"
4. Select: `Tylerberg45/ShopMasterOS`
5. Set root directory: `oil_change_tracker`
6. Railway will automatically build and deploy!

### Step 3: Configure Environment Variables (Optional)
In Railway dashboard → Variables tab, add:
- `ENVIRONMENT=production`
- `DEBUG=false`

### Step 4: Add Custom Domain (Optional)
- In Railway dashboard → Settings → Domains
- Add your custom domain or use Railway's provided URL

## 🔄 Auto-Deploy Setup
- Every `git push` to main branch automatically deploys
- No manual steps needed after initial setup
- Zero-downtime deployments

## 🗄️ Database Options

### Option A: Keep SQLite (Simple)
- Works immediately with your existing data
- Good for small business use
- Database file included in deployment

### Option B: Upgrade to PostgreSQL (Scalable)
1. In Railway dashboard → Add Service → Database → PostgreSQL
2. Railway automatically sets `DATABASE_URL`
3. Your app will switch to PostgreSQL automatically

## 📊 Monitoring
Railway dashboard provides:
- Real-time logs
- Performance metrics  
- Resource usage
- Deployment history

## 🔧 Troubleshooting
If deployment fails:
1. Check Railway logs in dashboard
2. Verify all files are committed to git
3. Ensure `oil_change_tracker` is set as root directory

## 💰 Cost Estimation
Railway free tier includes:
- 500 execution hours/month
- $5 credit for overages
- Should cover typical oil change shop usage

## 🔗 URLs After Deployment
- Production app: `https://your-app-name.railway.app`
- Health check: `https://your-app-name.railway.app/health`
- Dashboard: `https://your-app-name.railway.app/`
