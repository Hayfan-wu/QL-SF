# 顺丰全自动方案 - 完整部署指南
# =============================================

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         你的服务器（VPS）                             │
│                                                                     │
│  ┌──────────────────┐     自动提取Cookie     ┌──────────────────┐  │
│  │ DrissionPage      │ ───────────────────→  │ 中继跳板服务器    │  │
│  │ 浏览器自动化       │     定时(每1小时)       │ sf_token_relay   │  │
│  │ sf_cookie_        │     sessionId + ...    │ :5000            │  │
│  │ extractor.py      │                         │                  │  │
│  └──────────────────┘                         │  SQLite 存储      │  │
│       │                                        │  Cookie 有效性检测 │  │
│       │ 首次需扫码                               │  Web管理面板      │  │
│       ▼                                        │  过期推送通知      │  │
│  ┌──────────────────┐                         └────────┬─────────┘  │
│  │ Chromium 浏览器    │                                  │            │
│  │ (持久化用户数据)   │     GET /api/cookie              │            │
│  │ 一次扫码登录       │ ←───────────────────────────────┘            │
│  │ 后续自动复用       │                                           │
│  └──────────────────┘                                           │
│                                                                   │
│  ┌──────────────────┐     执行签到/任务/采蜜                        │
│  │ 青龙面板          │                                             │
│  │ 顺丰.py           │                                             │
│  │ cron: 51 8,21 * *│                                             │
│  └──────────────────┘                                           │
└───────────────────────────────────────────────────────────────────┘
```

## 为什么浏览器自动化能延长登录态？

| 对比项 | 单独的 Cookie | 浏览器持久化登录态 |
|--------|-------------|-------------------|
| 存储内容 | 只有 Cookie | Cookie + localStorage + sessionStorage + IndexedDB |
| Token刷新 | 无（过期就失效） | 浏览器自动执行 JS 刷新 token |
| 有效期 | 几小时~几天 | **可能数周甚至更长** |
| 为什么 | Cookie 是静态快照 | 浏览器是完整的运行环境，能响应服务端的刷新指令 |

**核心原理**：顺丰 H5 页面在浏览器中运行时，JavaScript 代码会自动管理 token 刷新。
只要浏览器保持运行、页面定期被访问，登录态就能持续续期。
这和你手动在手机上每天打开顺丰小程序是一样的效果。

---

## 部署步骤

### 第一步：安装依赖

```bash
pip install DrissionPage --break-system-packages
```

### 第二步：首次登录（只需做一次）

在服务器上执行：

```bash
python3 sf_cookie_extractor.py --login
```

**注意**：服务器需要有图形界面（X11/VNC）才能显示浏览器让你扫码。

**没有图形界面的服务器？** 有两个方案：

**方案 A：VNC 远程桌面（推荐）**
```bash
# 安装 VNC
apt install tigervnc-standalone-server -y
vncserver :1
# 设置密码后，用 VNC 客户端连接
# 在 VNC 桌面中打开终端执行：
python3 sf_cookie_extractor.py --login
```

**方案 B：在本地电脑登录，然后上传浏览器数据**
1. 在本地电脑安装 DrissionPage
2. 运行 `python3 sf_cookie_extractor.py --login`
3. 扫码登录成功后，将生成的 `browser_data/` 目录上传到服务器
4. 服务器后续运行会自动加载这个目录

### 第三步：启动 Cookie 自动提取守护进程

```bash
# 后台运行，每小时提取一次
nohup python3 sf_cookie_extractor.py --daemon \
  --relay http://localhost:5000 \
  --interval 3600 \
  > sf_extractor.log 2>&1 &
```

或者用 screen/tmux：
```bash
screen -S sf_extractor
python3 sf_cookie_extractor.py --daemon \
  --relay http://localhost:5000 \
  --interval 3600
# Ctrl+A, D 分离
```

### 第四步：启动中继跳板服务器

```bash
nohup python3 sf_token_relay.py --port 5000 > sf_relay.log 2>&1 &
```

### 第五步：配置青龙脚本

在青龙面板设置环境变量：
```
SF_RELAY_URL=http://localhost:5000
```

将修改后的 `顺丰.py` 上传到青龙，定时任务：
```
cron: 51 8,21 * * *
```

### 第六步：验证完整链路

```bash
# 检查提取器状态
tail -20 sf_extractor.log

# 检查中继服务器状态
curl http://localhost:5000/api/cookie

# 手动触发青龙脚本
# (在青龙面板点击运行)
```

---

## 配置推送通知（可选）

设置环境变量，Cookie 失效时自动通知你：

```bash
# 方式一：Bark（iOS 推荐）
export SF_BARK_KEY=你的Bark_Key

# 方式二：PushPlus（通用）
export SF_PUSHPLUS_TOKEN=你的PushPlus_Token
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `sf_cookie_extractor.py` | 浏览器自动化 Cookie 提取器（**新增，核心**） |
| `sf_token_relay.py` | 中继跳板服务器 |
| `顺丰.py`（修改版） | 青龙脚本，支持中继模式 |
| `sf_mobile_push.sh` | 手动推送 Cookie 脚本（备用） |
| `sf_relay_manager.py` | 运维管理工具 |
| `browser_data/` | DrissionPage 浏览器用户数据（登录态持久化） |
| `sf_cookies.json` | Cookie 本地备份 |

---

## 故障处理

| 问题 | 解决方案 |
|------|----------|
| 浏览器登录态失效 | 重新运行 `--login` 模式扫码 |
| 中继服务器无有效 Cookie | 检查提取器日志，确认是否在运行 |
| 青龙脚本报"中继无有效Cookie" | 手动执行 `--once` 模式提取一次 |
| VNC 连接失败 | 检查 VNC 端口是否开放，防火墙配置 |
| DrissionPage 启动失败 | 确认 Chromium/Chrome 已安装 |

---

## 一句话总结

**一次扫码 → 浏览器自动保持登录 → 每小时提取 Cookie → 青龙每天自动跑任务 → 过期自动通知你**

你需要手动做的只有一件事：**首次在 VNC 中扫码登录**。后续全自动运行，直到浏览器登录态最终失效（可能是几周后），才会收到通知让你重新扫码。