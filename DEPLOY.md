# 🚀 24/7 Free Cloud Deployment Guide

Follow these quick steps to get a permanent 24/7 URL for your iPhone (works even when your laptop is turned off or closed).

---

### Step 1: Push to GitHub (Takes 1 min)
1. Go to [github.com/new](https://github.com/new) and create a new repository called `prioritask` (can be Private or Public).
2. Copy the commands shown on GitHub and run them in your Terminal inside `todo_app`:
   ```bash
   cd ~/claude_angel/scalper/todo_app
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/prioritask.git
   git branch -M main
   git push -u origin main
   ```

---

### Step 2: Deploy Free on Render (Takes 2 mins)
1. Sign up / Log in to [render.com](https://render.com) (free).
2. Click **New +** $\rightarrow$ **Web Service**.
3. Select your `prioritask` repository from GitHub.
4. Settings:
   - **Name**: `prioritask` (or any name you like)
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python3 -m uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free ($0/month)
5. Click **Create Web Service**.

---

### Step 3: Open on iPhone & Add to Home Screen
Render will generate a permanent live link (e.g. `https://prioritask-xxxx.onrender.com`):
1. Open this link in **Safari on your iPhone**.
2. Tap the **Share** button $\rightarrow$ **Add to Home Screen**.
3. It will now work **24/7 on your iPhone**, whether your laptop is open, closed, or asleep, anywhere in the world on Wi-Fi or 4G/5G!
