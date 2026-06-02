# 双节点混合架构部署指南

> 美西 VPS（主站）+ 香港轻量（API 代理）+ CloudFlare CDN + Tunnel

---

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      欧美客户浏览器                          │
└──────────────┬──────────────────────────────┬───────────────┘
               │  HTML/CSS/JS/GLB             │  API 请求
               ▼                              ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│    CloudFlare CDN (全球)     │  │   CloudFlare DNS (代理模式)   │
│    静态资源边缘缓存          │  │   SSL 终结 + DDoS 防护       │
└──────────────────────────────┘  └──────────────┬───────────────┘
                                                 │
                                    ┌────────────┴────────────┐
                                    ▼                         ▼
                     ┌──────────────────────┐   ┌──────────────────────┐
                     │  美西 VPS (主站)      │   │  CloudFlare Tunnel   │
                     │  Vultr 洛杉矶 $6/月   │   │  (加密内网)          │
                     │                      │   │                      │
                     │  Flask + SQLite      │   │  /proxy/submit       │
                     │  Nginx + Gunicorn    │   │  /proxy/query        │
                     │  登录/聊天/文件管理   │──▶│                      │
                     └──────────────────────┘   └──────────┬───────────┘
                                                           │
                                                           ▼
                                              ┌──────────────────────┐
                                              │  香港轻量 (API代理)   │
                                              │  阿里云 HK ¥25/月    │
                                              │                      │
                                              │  hk_proxy.py         │
                                              │  转发到混元3D API    │
                                              │                      │
                                              │  30ms → 中国大陆     │
                                              └──────────────────────┘
```

---

## 第一步：购买服务器

### 美西 VPS（主站）

| 提供商 | 型号 | 配置 | 价格 | 机房 |
|--------|------|------|------|------|
| Vultr | Regular Cloud Compute | 1核 1G / 25G SSD / 1TB | $6/月 | 洛杉矶 |
| DigitalOcean | Basic Droplet | 1核 1G / 25G SSD / 1TB | $6/月 | 旧金山 |

推荐 Vultr 洛杉矶：按小时计费、新用户送 $100 试用金、支持支付宝。

### 香港轻量（API 代理）

| 提供商 | 型号 | 配置 | 价格 |
|--------|------|------|------|
| 阿里云 | 轻量应用服务器 国际型 | 2核 0.5G / 20G / 200M | ¥25/月 |

最低配即可 —— API 代理极省资源，0.5G 内存跑 gunicorn 2 worker 绰绰有余。

---

## 第二步：上传代码到两台服务器

```bash
# 在本地打包（排除不需要的文件）
cd ~/inflatable-website
tar -czf inflatable.tar.gz \
    --exclude='deploy' \
    --exclude='__pycache__' \
    --exclude='*.db*' \
    --exclude='flask_session' \
    --exclude='backups' \
    --exclude='ngrok.exe' \
    .

# 上传到两台服务器
scp inflatable.tar.gz root@<US_SERVER_IP>:~/
scp inflatable.tar.gz root@<HK_SERVER_IP>:~/

# 在每台服务器上解压
ssh root@<SERVER_IP> "mkdir -p /root/inflatable-website && cd /root/inflatable-website && tar -xzf ~/inflatable.tar.gz"
```

---

## 第三步：部署美西主站

SSH 到美西 VPS，执行：

```bash
# 1. 创建 .env 配置文件
nano /root/inflatable-website/.env
```

填入以下内容（**不要设置 HUNYUAN_PROXY_URL 先，确保单机模式能跑**）：

```ini
FLASK_SECRET_KEY=<生成一个随机字符串>
HUNYUAN_API_KEY=sk-kuuLt0xbnfj43TOlJ75EmlgY7vQbmAkz7w4aR9giDL78HtzX
HUNYUAN_ENDPOINT=https://api.ai3d.cloud.tencent.com
MAIL_SERVER=smtp.mxhichina.com
MAIL_PORT=465
MAIL_USERNAME=dulizhan@showlovein.com
MAIL_PASSWORD=<你的邮箱安全密码>
ADMIN_PASSWORD=<自己设置>
```

```bash
# 2. 运行部署脚本
chmod +x /root/inflatable-website/deploy/deploy-us.sh
bash /root/inflatable-website/deploy/deploy-us.sh
```

```bash
# 3. 验证
systemctl status inflatable-us
curl http://127.0.0.1:8000/
```

---

## 第四步：部署香港 API 代理

SSH 到香港轻量，执行：

```bash
# 1. 生成代理密钥
PROXY_SECRET=$(openssl rand -hex 32)
echo "Proxy secret: $PROXY_SECRET"  # 记下来

# 2. 运行部署脚本
chmod +x /root/inflatable-website/deploy/deploy-hk.sh
bash /root/inflatable-website/deploy/deploy-hk.sh
```

```bash
# 3. 编辑 .env，替换 PROXY_SECRET
nano /opt/inflatable-hk/.env
# 将 REPLACE_WITH_RANDOM_SECRET 替换为上面生成的 proxy secret
```

```bash
# 4. 重启并验证
systemctl restart inflatable-hk
curl http://127.0.0.1:8080/health
# 预期返回: {"status":"ok"}
```

---

## 第五步：配置 CloudFlare Tunnel（香港 → 美西安全内网）

### 5.1 在香港服务器安装 cloudflared

```bash
# 下载并安装
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
```

### 5.2 在 CloudFlare Dashboard 创建 Tunnel

1. 登录 [CloudFlare Zero Trust](https://one.dash.cloudflare.com/)
2. `Networks` → `Tunnels` → `Create a tunnel`
3. 名称：`hk-api-proxy`
4. 选择 Linux，复制安装命令在香港服务器执行：

```bash
cloudflared service install <TOKEN>
```

### 5.3 配置 Tunnel 路由

在 CloudFlare Dashboard 中，为该 Tunnel 添加 Public Hostname：

| Public Hostname | Service |
|-----------------|---------|
| `hk-proxy.yourdomain.com` | `http://localhost:8080` |

**重要**：在 Public Hostname 配置中启用「Protect with Access」可选，不启用则直接暴露。建议启用 Access 的 Service Token 做服务间认证，或依赖 `X-Proxy-Secret` 做应用层鉴权。

### 5.4 验证 Tunnel 连通

```bash
# 从美西 VPS 测试
ssh root@<US_SERVER_IP>
curl -X POST https://hk-proxy.yourdomain.com/proxy/submit \
  -H "Content-Type: application/json" \
  -H "X-Proxy-Secret: <你的 PROXY_SECRET>" \
  -d '{"Model":"3.0","Prompt":"test"}'
```

如果返回 JSON 响应（含 `JobId`），说明代理链连通。

---

## 第六步：激活双节点模式

### 6.1 更新美西主站 .env

```bash
ssh root@<US_SERVER_IP>
nano /opt/inflatable-website/.env
```

追加两行（**用实际值替换**）：

```ini
HUNYUAN_PROXY_URL=https://hk-proxy.yourdomain.com
HUNYUAN_PROXY_SECRET=<第二步生成的 PROXY_SECRET>
```

### 6.2 重启美西主站

```bash
systemctl restart inflatable-us
systemctl status inflatable-us
journalctl -u inflatable-us -f  # 观察启动日志
```

---

## 第七步：配置 CloudFlare DNS + CDN

### 7.1 DNS 配置

在 CloudFlare Dashboard → DNS → Records：

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `<美西 VPS IP>` | Proxied（橙色云） |
| A | `www` | `<美西 VPS IP>` | Proxied（橙色云） |
| CNAME | `hk-proxy` | `<Tunnel UUID>.cfargotunnel.com` | Proxied（橙色云） |

### 7.2 SSL/TLS 设置

CloudFlare → SSL/TLS → Overview → 选择 **Full (strict)**。

### 7.3 缓存规则

CloudFlare → Caching → Cache Rules → 新建规则：

| 规则 | URI 路径 | 缓存时长 |
|------|----------|----------|
| 静态资源 | `/static/*` | 30 天 |
| 模型文件 | `/uploads/models/*` | 7 天 |
| 上传图片 | `/uploads/chat/*` | 1 天 |
| API 请求 | `/api/*` | 不缓存 |

### 7.4 速度优化

CloudFlare → Speed → Optimization：
- Auto Minify: 全部开启（JS/CSS/HTML）
- Brotli: 开启
- Rocket Loader: 开启（如前端正常则保留）
- Early Hints: 开启
- HTTP/3: 开启

---

## 第八步：验证完整链路

```bash
# 1. 首页访问
curl -I https://www.yourdomain.com/
# 预期: HTTP/2 200, cf-cache-status: HIT/MISS, server: cloudflare

# 2. 3D 生成（需要先登录）
# 在浏览器中完成完整流程：注册 → 验证 → 登录 → 上传图片 → 生成3D

# 3. 检查代理是否生效
ssh root@<US_SERVER_IP>
journalctl -u inflatable-us -f | grep proxy
# 观察 3D 请求是否走 /proxy/submit
```

---

## 常用运维命令

```bash
# === 美西主站 ===
systemctl status inflatable-us        # 服务状态
journalctl -u inflatable-us -f        # 实时日志
journalctl -u inflatable-us -n 50     # 最近 50 行
systemctl restart inflatable-us       # 重启
systemctl stop inflatable-us          # 停止

# === 香港代理 ===
systemctl status inflatable-hk
journalctl -u inflatable-hk -f
systemctl restart inflatable-hk

# === Nginx ===
nginx -t                              # 测试配置
systemctl reload nginx                # 热重载
tail -f /var/log/nginx/access.log     # 访问日志

# === CloudFlare Tunnel ===
systemctl status cloudflared
cloudflared tunnel list               # 列出所有 tunnel
cloudflared tunnel info hk-api-proxy  # 查看 tunnel 详情
```

---

## 单节点回退

如果香港代理出问题，清空两行即可回退到美西直连模式：

```bash
ssh root@<US_SERVER_IP>
nano /opt/inflatable-website/.env
# 注释或删除:
# HUNYUAN_PROXY_URL=
# HUNYUAN_PROXY_SECRET=
systemctl restart inflatable-us
```

---

## 成本汇总

| 项目 | 月费 | 年费 |
|------|------|------|
| Vultr 洛杉矶 1核1G | $6.00 | $72.00 |
| 阿里云香港轻量 2核0.5G | ¥25.00 | ¥300.00 |
| CloudFlare CDN（Free） | $0 | $0 |
| 域名 .com | — | ~$10.00 |
| **合计** | **≈$9.50** | **≈$112.00** |
