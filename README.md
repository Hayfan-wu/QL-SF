# QL-SF - 顺丰速运自动化

顺丰速运积分任务自动化脚本，支持**青龙面板定时运行** + **QQ 机器人交互控制**。

**v2.0**：参考 QL-DX 模式重构，独立仓库、独立配置，QL-Bot 自动扫描加载，绝不修改 QL-Bot 任何文件。

## 功能

| 功能 | 说明 |
|---|---|
| 每日签到 | 自动签到领积分 |
| 超值福利 | 超值福利签到领红包 |
| 任务列表 | 自动完成积分任务 |
| 周年庆活动 | 周年庆相关活动自动参与 |
| 会员日任务 | 会员日专属任务 |
| 多账号支持 | 多账号换行分隔 |
| QQ 交互 | 通过 QL-Bot 机器人交互控制 |

## 依赖

```bash
pip install requests
```

## 青龙面板

1. 克隆仓库到青龙脚本目录：
```bash
cd /ql/data/scripts
git clone https://github.com/Hayfan-wu/QL-SF.git
cd QL-SF
cp .env.example .env
```

2. 在青龙面板添加定时任务：
- 任务名: SF-Express
- 命令: `task QL-SF/顺丰.py`
- 定时: `10 12 * * *`

## QQ 机器人

配合 [QL-Bot](https://github.com/Hayfan-wu/QL-Bot) 使用，自动扫描 `/opt/QL-SF/bot_plugins/` 加载插件。

| 命令 | 功能 |
|---|---|
| `顺丰` / `顺丰菜单` | 帮助菜单 |
| `顺丰登录` | 多轮引导设置 sfsyUrl，自动提交青龙 |
| `顺丰状态` | 查看 sfsyUrl 配置状态 |
| `顺丰更新 [内容]` | 手动更新 sfsyUrl 或 Cookie |
| `顺丰执行` | 手动执行全部任务 |

## 项目结构

```
QL-SF/
├── 顺丰.py              # 青龙定时任务入口
├── .env                 # 环境变量（git不追踪）
├── .env.example         # 环境变量模板
├── bot_plugins/         # QQ机器人插件
│   └── sf_plugin.py     # 交互逻辑
├── docker/              # Docker 高级方案（可选）
│   ├── sf-relay/        # 中继服务器
│   └── sf-extractor/    # Cookie自动提取
├── docker-compose.yml   # Docker编排（可选）
├── sf_token_relay.py    # 中继服务器（可选）
├── sf_cookie_extractor.py  # Cookie提取器（可选）
└── README.md
```

## 两种使用模式

### 模式一：简单模式（推荐）

直接通过 QQ 机器人配置 sfsyUrl，脚本每日定时运行。

```
QQ 发送: 顺丰登录
按提示粘贴 sfsyUrl → 自动保存并提交青龙
```

sfsyUrl 获取方式：
- 顺丰APP绑定微信后，前往 [sm.linzixuan.work](http://sm.linzixuan.work) 扫码复制
- 或打开小程序/APP-我的-积分，手动抓包 URL

### 模式二：Docker 高级模式（可选）

如需全自动 Cookie 刷新（无需手动更新），可部署 Docker 方案：

```bash
cd /opt/QL-SF
docker compose up -d
```

详见 [FULL_AUTO_GUIDE.md](FULL_AUTO_GUIDE.md)

## 注意事项

- `sfsyUrl` 是脚本核心参数，失效后需重新获取
- 简单模式下 Cookie 通常可存活数天至数周
- Docker 高级模式通过浏览器自动化维持 Cookie，实现全自动运行
- 项目 `.env` 独立管理，不修改 QL-Bot 的 `.env`
