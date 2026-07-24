# QL-SF 顺丰全自动方案

> 一次扫码，全自动运行。Cookie 失效时 QQ 机器人提醒你重新扫码。

## 快速开始

```bash
# 1. 克隆到服务器
cd /opt
git clone https://github.com/Hayfan-wu/QL-SF.git
cd QL-SF

# 2. 一键安装
chmod +x easy-install.sh
sudo bash easy-install.sh

# 3. 改密码
nano .env

# 4. 重启
docker compose -f docker-compose-simple.yml restart

# 5. 首次扫码登录
docker compose -f docker-compose-simple.yml --profile login up -d sf-login
# 浏览器打开 http://服务器IP:6080/vnc.html 密码 sf123456
```

详细教程见 [EASY_GUIDE.md](EASY_GUIDE.md)

## QQ 机器人命令

| 命令 | 作用 |
|------|------|
| `/顺丰` | 查看Cookie状态 |
| `/顺丰登录` | 启动扫码登录 |
| `/顺丰更新` | 手动推送Cookie |
| `/顺丰帮助` | 查看帮助 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `docker-compose-simple.yml` | 极简版Docker编排 |
| `easy-install.sh` | 一键安装脚本 |
| `sf_token_relay.py` | 中继服务器（存储Cookie + Web管理） |
| `sf_cookie_extractor.py` | Cookie自动提取器（浏览器自动化） |
| `bot_plugins/sf.py` | QL-Bot QQ机器人插件 |
| `顺丰.py` | 青龙脚本（已支持中继模式） |
| `EASY_GUIDE.md` | 傻瓜式教程 |
