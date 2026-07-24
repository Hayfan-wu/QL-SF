# 顺丰全自动方案 - 傻瓜式教程

> 目标：**你只管扫码一次，之后全自动运行，直到失效提醒你重新扫码。**

---

## 需要什么

| 项目 | 说明 |
|------|------|
| 一台 Debian 12 服务器 | 有 root 权限，能访问外网 |
| Docker | 会自动帮你安装 |
| 青龙面板 | 已有，用来跑脚本 |
| 一个QQ机器人 | 可选但强烈推荐，用来交互 |
| 手机微信 | 用来扫码登录顺丰 |

---

## 一句话原理

```
你扫码一次 -> 服务器记住你的微信登录态
         -> 每小时自动帮你"打开"顺丰小程序（刷新Cookie）
         -> 青龙每天自动签到/做任务
         -> Cookie失效了QQ机器人喊你重新扫码
```

---

## 第一步：下载项目到服务器

用 `root` 账号登录服务器，执行：

```bash
cd /opt
git clone https://github.com/你的仓库/QL-SF.git
# 如果没有git仓库，直接把项目文件上传到 /opt/QL-SF/
cd /opt/QL-SF
```

---

## 第二步：一键安装（全自动）

```bash
chmod +x easy-install.sh
sudo bash easy-install.sh
```

脚本会自动：
- [x] 检查/安装 Docker
- [x] 构建镜像
- [x] 启动中继服务器 + Cookie提取器
- [x] 生成 `.env` 配置文件

完成后会显示你的服务器IP和管理面板地址。

---

## 第三步：改个密码（30秒）

```bash
nano /opt/QL-SF/.env
```

把 `SF_RELAY_TOKEN` 改成你自己记得住的随机字符串：

```
SF_RELAY_TOKEN=MySecretToken2024
```

按 `Ctrl+O` 保存，`Ctrl+X` 退出。

然后重启一下：

```bash
cd /opt/QL-SF
docker compose -f docker-compose-simple.yml restart
```

---

## 第四步：首次扫码登录

### 方式A：直接浏览器扫码（不用QQ机器人）

```bash
cd /opt/QL-SF
docker compose -f docker-compose-simple.yml --profile login up -d sf-login
```

然后在电脑浏览器打开：

```
http://你的服务器IP:6080/vnc.html
```

密码：`sf123456`

你会看到一个手机大小的浏览器窗口，里面打开着顺丰页面，**用手机微信扫码登录**即可。

登录成功后，这个容器会自动把Cookie保存好。

---

### 方式B：配合QQ机器人扫码（推荐）

如果你已经部署了 [QL-Bot](https://github.com/Hayfan-wu/QL-Bot)，直接把 `bot_plugins/sf.py` 放到你的项目里：

```bash
# 假设你的 QL-Bot 在 /opt/QL-Bot
# 假设 QL-SF 在 /opt/QL-SF
ln -s /opt/QL-SF/bot_plugins /opt/QL-SF-bot
```

然后在QQ群里发送：

```
/顺丰登录
```

机器人会回复：

```
登录服务已启动！
================================
1. 在电脑浏览器打开:
   http://服务器IP:6080/vnc.html
2. 密码: sf123456
3. 在浏览器窗口中用手机微信扫码登录顺丰
4. 登录成功后Cookie会自动保存
================================
登录完成后发送 /顺丰 查看状态
```

你按提示操作即可，全程不用SSH登录服务器。

---

## 第五步：验证登录成功

QQ群里发送：

```
/顺丰
```

机器人回复类似：

```
顺丰Cookie状态
  [1] 138****4746 - 有效
      更新: 2026-07-24 10:30:15
```

看到 `有效` 就说明成功了！

---

## 第六步：配置青龙面板

在青龙面板添加两个环境变量：

| 变量名 | 值 |
|--------|-----|
| `SF_RELAY_URL` | `http://服务器IP:5000` |
| `SF_RELAY_TOKEN` | 你在 `.env` 里填的密码 |

然后把修改过的 `顺丰.py` 上传到青龙脚本目录，添加定时任务：

```
cron: 51 8,21 * * *
```

### 让青龙能访问中继

如果青龙也是Docker容器，需要加入同一网络：

```bash
docker network connect sf-network qinglong
```

然后把 `SF_RELAY_URL` 改成 `http://sf-relay:5000`。

---

## 完成了！之后全自动

| 时间点 | 发生什么 |
|--------|----------|
| 每天 8:51 / 21:51 | 青龙自动跑顺丰签到和任务 |
| 每小时 | Cookie提取器自动刷新登录态 |
| Cookie失效时 | QQ机器人@你提醒，或推送通知 |

你只需要在Cookie失效时重新执行 `/顺丰登录` 扫码即可，可能几周才需要一次。

---

## QQ机器人常用命令

| 命令 | 作用 |
|------|------|
| `/顺丰` | 查看Cookie状态 |
| `/顺丰登录` | 启动扫码登录 |
| `/顺丰更新` | 手动推送Cookie |
| `/顺丰帮助` | 查看帮助 |

---

## 常见问题

**Q: 扫码后还是显示失效？**

A: 等1-2分钟再发 `/顺丰` 查看，因为Cookie验证需要时间。如果还是失效，可能是微信登录态本身过期了，重新扫码。

**Q: 不想用QQ机器人，怎么手动推送Cookie？**

A: 在手机上用 Stream/HttpCanary 抓包获取Cookie，然后：

```bash
curl -X POST http://服务器IP:5000/api/update \
  -H "Content-Type: application/json" \
  -d '{"cookie":"_login_mobile_=xxx; _login_user_id_=xxx; sessionId=xxx"}'
```

**Q: 怎么看日志排查问题？**

```bash
cd /opt/QL-SF
docker compose -f docker-compose-simple.yml logs -f
```

**Q: 怎么停止所有服务？**

```bash
cd /opt/QL-SF
docker compose -f docker-compose-simple.yml down
```

**Q: 怎么重启？**

```bash
cd /opt/QL-SF
docker compose -f docker-compose-simple.yml restart
```

---

## 文件结构

```
/opt/QL-SF/
├── docker-compose-simple.yml   # Docker编排
├── easy-install.sh             # 一键安装
├── .env                        # 你的配置
├── sf_token_relay.py           # 中继服务器源码
├── sf_cookie_extractor.py      # Cookie提取器源码
├── bot_plugins/
│   ├── sf.py                   # QQ机器人插件
│   └── .env                    # 插件配置
└── docker/                     # Dockerfile目录
    ├── sf-relay/
    ├── sf-extractor/
    └── sf-extractor/noVNC/
```

---

## 总结

| 步骤 | 操作 | 频率 |
|------|------|------|
| 安装 | `bash easy-install.sh` | 一次 |
| 配置密码 | 改 `.env` 里的 Token | 一次 |
| 扫码登录 | `/顺丰登录` 或浏览器打开6080 | Cookie失效时（几周一次） |
| 日常使用 | 全自动，无需操作 | 每天 |

**你唯一需要手动做的：Cookie失效时，在QQ群发 `/顺丰登录`，扫码。**
