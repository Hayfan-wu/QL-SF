# QL-SF - 顺丰速运自动化

顺丰速运积分任务自动化脚本，支持**青龙面板定时运行** + **QQ 机器人交互控制** + **Docker 全自动 Cookie 刷新**。

参考 QL-DX 部署模式，独立仓库、独立配置，QL-Bot 自动扫描加载，绝不修改 QL-Bot 任何文件。

## 功能

| 功能 | 说明 |
|---|---|
| 每日签到 | 自动签到领积分 |
| 超值福利 | 超值福利签到领红包 |
| 任务列表 | 自动完成积分任务 |
| 周年庆/会员日 | 活动自动参与 |
| 多账号 | 换行分隔 |
| QQ 交互 | QL-Bot 机器人控制 |
| Docker Cookie | 自动刷新，免手动维护 |

## 两种模式

| | 简单模式 | Docker 全自动 |
|--|---------|--------------|
| Cookie 来源 | 手动粘贴 sfsyUrl | 浏览器自动刷新 |
| 维护频率 | 过期需重新获取 | 一次扫码，永久运行 |
| 部署方式 | 青龙 + QQ 机器人 | Portainer Stacks |

---

## 模式一：简单模式

### 青龙面板

1. 青龙面板 → 脚本管理 → 新建目录 `QL-SF`
2. 上传 `顺丰.py` 到 `QL-SF/` 目录
3. 环境变量 → 添加 `sfsyUrl`（值填你抓包得到的 URL）
4. 定时任务 → 新建：
   - 名称: `SF-Express`
   - 命令: `task QL-SF/顺丰.py`
   - 定时: `10 12 * * *`

### QQ 机器人

配合 [QL-Bot](https://github.com/Hayfan-wu/QL-Bot) 使用，自动扫描 `/opt/QL-SF/bot_plugins/` 加载插件。

| 命令 | 功能 |
|---|---|
| `顺丰` / `顺丰菜单` | 帮助菜单 |
| `顺丰登录` | 设置 sfsyUrl，自动提交青龙 |
| `顺丰状态` | 查看配置状态 |
| `顺丰更新 [内容]` | 手动更新 sfsyUrl |
| `顺丰执行` | 手动执行全部任务 |

---

## 模式二：Docker 全自动（Portainer）

### 前置条件

- Portainer 2.x 已安装运行
- 青龙面板已部署（Docker 方式）
- QL-Bot 已配置好

### 第一步：Portainer 添加 Stack

1. 打开 Portainer → **Stacks** → **Add stack**
2. 填写：
   - **Name**: `ql-sf`
   - **Build method**: **Repository**
   - **Repository URL**: `https://github.com/Hayfan-wu/QL-SF.git`
   - **Compose path**: `docker-compose.yml`（默认）
3. 点击 **Add environment variable**，添加：
   - `SF_RELAY_TOKEN` = 随便填一串16位以上字符串
4. 点击 **Deploy the stack**

等待构建完成（首次约 3-5 分钟），确认 `sf-relay` 和 `sf-extractor` 状态为 running。

### 第二步：连接青龙到 sf-network

Portainer → 任意一个青龙容器 → **Inspect** → **Network** → 找到青龙的网络名称

然后在 Portainer → **Containers** → `sf-relay` → **Inspect** → **Network** 确认在 `sf-network`

在 Portainer 的 **Console** 中执行（任意容器）：

```bash
docker network connect sf-network 你的青龙容器名
```

### 第三步：首次扫码登录

1. Portainer → Containers → 找到 `sf-login`（状态是 Stopped/Exited）
2. 点击 **Start** 启动它
3. 浏览器打开 `http://服务器IP:6080/vnc.html`
4. 输入密码 `sf123456`
5. 在浏览器窗口中用手机微信扫码登录顺丰
6. 登录成功后回到 Portainer → `sf-login` → **Stop**

### 第四步：青龙面板配置

环境变量 → 添加：

| 名称 | 值 |
|------|-----|
| `SF_RELAY_URL` | `http://sf-relay:5000` |
| `SF_RELAY_TOKEN` | 你填的 Token |
| `sfsyUrl` | 任意占位值（脚本需要此变量） |

定时任务 → 新建：
- 名称: `SF-Express`
- 命令: `task QL-SF/顺丰.py`
- 定时: `10 12 * * *`

### 第五步：切换 QQ 机器人插件

Docker 模式需要使用中继版插件：

```bash
cd /opt/QL-SF/bot_plugins
mv sf_plugin.py sf_plugin.py.bak
cp archive/sf_docker.py sf.py
```

然后重启 QL-Bot。

---

## 项目结构

```
QL-SF/
├── 顺丰.py              # 青龙定时任务入口
├── docker-compose.yml   # Docker 编排（Portainer 用这个）
├── .env.example         # 环境变量模板
├── bot_plugins/         # QQ 机器人插件
│   ├── sf_plugin.py     # 简单模式插件
│   └── archive/
│       └── sf_docker.py # Docker 模式插件
├── docker/
│   ├── sf-relay/        # 中继服务器
│   ├── sf-extractor/    # Cookie 提取器
│   │   └── noVNC/       # 扫码登录器
├── sf_token_relay.py    # 中继服务器源码
└── sf_cookie_extractor.py  # 提取器源码
```

## 注意事项

- Docker 模式下 `sf-extractor` 每小时自动刷新 Cookie，无需手动干预
- `sf-browser-data` 卷存储浏览器登录态，**删除此卷等于重新扫码**
- 简单模式和 Docker 模式的 QQ 插件不能同时加载，切换时需备份另一个
