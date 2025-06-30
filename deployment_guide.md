# 🚀 VIBES UNIVERSITY PLATFORM - DEPLOYMENT GUIDE

## 📋 **Pre-Deployment Checklist**

### ✅ **Before You Deploy**
1. **Test locally** - Run `python test_local_platform.py`
2. **Set environment variables** - Create `.env` file with real values
3. **Upload course content** - Use admin panel to add lessons
4. **Configure payment gateways** - Set up Paystack/Flutterwave keys
5. **Test payment flow** - Verify end-to-end payment → access

---

## 🎯 **Recommended Deployment Options**

### **Option 1: Render (Recommended - Easiest)**

**Why Render?**
- ✅ **Free tier available** (with limitations)
- ✅ **Automatic HTTPS**
- ✅ **Easy database setup**
- ✅ **Git integration**
- ✅ **Custom domains**

**Steps:**
1. **Sign up** at [render.com](https://render.com)
2. **Connect GitHub** repository
3. **Create Web Service**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Environment**: Python 3.9+
4. **Add Environment Variables**:
   ```
   FLASK_ENV=production
   SECRET_KEY=your-super-secret-key
   PAYSTACK_SECRET_KEY=sk_live_your_key
   FLUTTERWAVE_SECRET_KEY=FLWSECK_your_key
   ```
5. **Deploy** - Automatic deployment from Git

**Cost**: Free tier → $7/month for paid plan

---

### **Option 2: Railway (Fast & Reliable)**

**Why Railway?**
- ✅ **Very fast deployment**
- ✅ **Automatic scaling**
- ✅ **Database included**
- ✅ **Git integration**

**Steps:**
1. **Sign up** at [railway.app](https://railway.app)
2. **Connect GitHub** repository
3. **Add PostgreSQL** database (free tier)
4. **Deploy** - Automatic deployment
5. **Set environment variables** in dashboard

**Cost**: $5/month (includes database)

---

### **Option 3: Heroku (Traditional Choice)**

**Why Heroku?**
- ✅ **Mature platform**
- ✅ **Great documentation**
- ✅ **Add-ons ecosystem**

**Steps:**
1. **Install Heroku CLI**
2. **Create app**: `heroku create vibes-university`
3. **Add PostgreSQL**: `heroku addons:create heroku-postgresql:mini`
4. **Set environment variables**:
   ```bash
   heroku config:set FLASK_ENV=production
   heroku config:set SECRET_KEY=your-secret-key
   heroku config:set PAYSTACK_SECRET_KEY=sk_live_your_key
   ```
5. **Deploy**: `git push heroku main`

**Cost**: $7/month (basic dyno) + $5/month (database)

---

### **Option 4: VPS (Complete Control)**

**Why VPS?**
- ✅ **Complete control**
- ✅ **Lowest cost for high traffic**
- ✅ **Custom domain setup**
- ✅ **Full server access**

**Recommended Providers:**
- **DigitalOcean** ($6/month)
- **Linode** ($5/month)
- **Vultr** ($5/month)
- **AWS EC2** (pay-as-you-go)

**Steps:**
1. **Create VPS** (Ubuntu 20.04+)
2. **Install dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip nginx
   ```
3. **Clone repository**:
   ```bash
   git clone https://github.com/yourusername/vibes-university.git
   cd vibes-university
   ```
4. **Install Python dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```
5. **Set up environment**:
   ```bash
   cp env_template.txt .env
   # Edit .env with your values
   ```
6. **Set up Gunicorn**:
   ```bash
   pip3 install gunicorn
   ```
7. **Create systemd service**:
   ```bash
   sudo nano /etc/systemd/system/vibes-university.service
   ```
   ```ini
   [Unit]
   Description=Vibes University Platform
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/vibes-university
   Environment="PATH=/home/ubuntu/vibes-university/venv/bin"
   ExecStart=/home/ubuntu/vibes-university/venv/bin/gunicorn --workers 3 --bind unix:vibes-university.sock -m 007 app:app

   [Install]
   WantedBy=multi-user.target
   ```
8. **Start service**:
   ```bash
   sudo systemctl start vibes-university
   sudo systemctl enable vibes-university
   ```
9. **Configure Nginx**:
   ```bash
   sudo nano /etc/nginx/sites-available/vibes-university
   ```
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           include proxy_params;
           proxy_pass http://unix:/home/ubuntu/vibes-university/vibes-university.sock;
       }
   }
   ```
10. **Enable site**:
    ```bash
    sudo ln -s /etc/nginx/sites-available/vibes-university /etc/nginx/sites-enabled
    sudo nginx -t
    sudo systemctl restart nginx
    ```
11. **Set up SSL** (Let's Encrypt):
    ```bash
    sudo apt install certbot python3-certbot-nginx
    sudo certbot --nginx -d yourdomain.com
    ```

**Cost**: $5-10/month (VPS) + domain ($10-15/year)

---

## 🔧 **Production Configuration**

### **Environment Variables (Required)**
```bash
# Production settings
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=your-super-secret-production-key

# Payment gateways (REAL keys, not test)
PAYSTACK_SECRET_KEY=sk_live_your_real_paystack_key
FLUTTERWAVE_SECRET_KEY=FLWSECK_your_real_flutterwave_key

# Email settings
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Admin password
ADMIN_PASSWORD=your-secure-admin-password

# Website URLs
WEBSITE_URL=https://yourdomain.com
API_URL=https://yourdomain.com/api
```

### **Security Checklist**
- ✅ **Change default admin password**
- ✅ **Use HTTPS everywhere**
- ✅ **Set strong SECRET_KEY**
- ✅ **Enable database backups**
- ✅ **Set up monitoring**

---

## 📊 **Performance Optimization**

### **For High Traffic**
1. **Database**: Use PostgreSQL instead of SQLite
2. **Caching**: Add Redis for session storage
3. **CDN**: Use CloudFlare for static files
4. **Load Balancing**: Multiple server instances

### **File Storage**
- **Local**: Good for small files
- **AWS S3**: Recommended for videos
- **CloudFlare R2**: Alternative to S3
- **DigitalOcean Spaces**: Simple S3-compatible

---

## 🚨 **Post-Deployment Checklist**

### **Immediate Actions**
1. **Test all functionality**:
   - Landing page loads
   - Payment flow works
   - Admin upload works
   - Student access works
2. **Set up monitoring**:
   - Uptime monitoring
   - Error logging
   - Performance tracking
3. **Configure backups**:
   - Database backups
   - File backups
   - Configuration backups

### **Security Hardening**
1. **Change default passwords**
2. **Set up firewall rules**
3. **Enable rate limiting**
4. **Monitor access logs**

---

## 💰 **Cost Comparison**

| Platform | Monthly Cost | Database | SSL | Custom Domain |
|----------|-------------|----------|-----|---------------|
| **Render** | $7 | ✅ | ✅ | ✅ |
| **Railway** | $5 | ✅ | ✅ | ✅ |
| **Heroku** | $12 | ✅ | ✅ | ✅ |
| **VPS** | $5-10 | ✅ | ✅ | ✅ |

**Recommendation**: Start with **Render** (easiest), then migrate to **VPS** when you have 100+ students.

---

## 🎯 **Quick Start Commands**

### **Local Testing**
```bash
# Start the platform
python app.py

# Run tests
python test_local_platform.py

# Test admin upload
# Go to http://localhost:5000/admin/login
# Password: vibesadmin123
```

### **Deploy to Render**
```bash
# 1. Push to GitHub
git add .
git commit -m "Ready for deployment"
git push origin main

# 2. Connect to Render
# - Go to render.com
# - Connect GitHub repo
# - Deploy automatically
```

### **Deploy to VPS**
```bash
# 1. SSH to your server
ssh user@your-server-ip

# 2. Clone and setup
git clone https://github.com/yourusername/vibes-university.git
cd vibes-university
pip3 install -r requirements.txt

# 3. Configure and start
cp env_template.txt .env
# Edit .env with your values
python3 app.py
```

---

## 🎉 **You're Ready to Deploy!**

Your Vibes University platform is **production-ready** with:
- ✅ **Complete payment integration**
- ✅ **Admin upload system**
- ✅ **Student course platform**
- ✅ **Progress tracking**
- ✅ **Security controls**

**Choose your deployment option and launch your course platform!** 🚀 