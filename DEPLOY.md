# InflatableModel.CN 部署方案

## 方案概述

用户已购买域名，后续购买服务器部署本项目。以下提供两种部署方案，推荐方案 A。

---

## 方案 A：轻量应用服务器（腾讯云 Lighthouse）[推荐]

### 推荐配置

| 配置项 | 建议 |
|--------|------|
| CPU / 内存 | 2 核 2G（起步） |
| 系统盘 | 40GB SSD |
| 操作系统 | CentOS 7.6 或 Ubuntu 22.04 LTS |
| 带宽 | 3-5 Mbps |

### 部署架构

```
用户浏览器 → Nginx (80/443, SSL 终止, 静态文件) → Gunicorn (127.0.0.1:8000) → Flask App
                                                                                   ↓
                                                                              SQLite (data.db)
```

- **Nginx**：反向代理 + SSL 终止 + 静态文件服务
- **Gunicorn**：WSGI 应用服务器，多 worker 处理并发
- **Supervisor**：进程守护，自动重启

### 部署步骤

#### 1. 环境安装

```bash
# Ubuntu
sudo apt update && sudo apt install -y python3 python3-pip nginx supervisor

# 安装 Python 依赖
cd /opt/inflatable-website
pip3 install -r requirements.txt
```

#### 2. 代码上传

```bash
# 将项目上传至服务器
scp -r inflatable-website/ root@<服务器IP>:/opt/
```

#### 3. Gunicorn 配置

创建 `/opt/inflatable-website/gunicorn.conf.py`：

```python
bind = "127.0.0.1:8000"
workers = 2
worker_class = "sync"
timeout = 120
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
```

#### 4. Nginx 反向代理

创建 `/etc/nginx/sites-available/inflatablemodel`：

```nginx
server {
    listen 80;
    server_name inflatablemodel.cn www.inflatablemodel.cn;

    client_max_body_size 64M;

    location /static/ {
        alias /opt/inflatable-website/static/;
        expires 30d;
    }

    location /uploads/ {
        alias /opt/inflatable-website/uploads/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

启用配置：

```bash
ln -s /etc/nginx/sites-available/inflatablemodel /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

#### 5. SSL 配置（Let's Encrypt）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d inflatablemodel.cn -d www.inflatablemodel.cn
# 选择自动重定向 HTTP → HTTPS
```

证书自动续期：

```bash
sudo certbot renew --dry-run  # 测试
# certbot 自带 systemd timer 自动续期
```

#### 6. Supervisor 守护

创建 `/etc/supervisor/conf.d/inflatablemodel.conf`：

```ini
[program:inflatablemodel]
command=/usr/bin/python3 /opt/inflatable-website/app.py
directory=/opt/inflatable-website
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/inflatablemodel.log
```

启动：

```bash
supervisorctl reread
supervisorctl update
supervisorctl start inflatablemodel
```

#### 7. 安全组配置

在腾讯云控制台开放以下端口：

| 端口 | 协议 | 说明 |
|------|------|------|
| 22 | TCP | SSH 管理 |
| 80 | TCP | HTTP |
| 443 | TCP | HTTPS |

---

## 方案 B：Serverless（腾讯云 CloudBase）

### 优点

- 免运维，无需管理服务器
- 按量付费，低流量时成本极低
- 自动扩缩容，高并发无压力

### 缺点

- 需要将 Flask 改造为云函数（每个路由一个函数）
- SQLite 不适用，需迁移至云数据库（TDSQL / MySQL）
- 文件存储需使用云存储（COS）
- 冷启动延迟（首次请求较慢）
- 改造工作量较大

---

## 预估月费用

| 方案 | 配置 | 月费估算 |
|------|------|----------|
| A：Lighthouse | 2C2G, 40GB, 3Mbps | 约 ¥50-70/月 |
| B：CloudBase | 云函数 + 云数据库 + COS | 低流量 ¥10-30/月；中流量 ¥50-100/月 |

---

## 部署前检查清单

- [ ] 域名已备案（中国大陆服务器必须备案）
- [ ] SSL 证书已申请（Let's Encrypt 或腾讯云免费证书）
- [ ] 安全组端口 80 / 443 已开放
- [ ] 数据库备份机制就绪（SQLite 定期备份到 COS）
- [ ] requirements.txt 依赖完整
- [ ] `config.py` 中生产环境配置已更新（SESSION_SECRET_KEY 等）
- [ ] Google OAuth Client ID 已替换为实际值
- [ ] 腾讯云 3D 生成 API 密钥已配置
- [ ] 上传目录 `uploads/chat/` 可写权限正确

---

## 日常运维

```bash
# 查看服务状态
supervisorctl status inflatablemodel

# 重启服务
supervisorctl restart inflatablemodel

# 查看日志
tail -f /var/log/inflatablemodel.log
tail -f /var/log/gunicorn/error.log

# 备份数据库
cp /opt/inflatable-website/data.db /backup/data_$(date +%Y%m%d).db
```