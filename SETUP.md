# 顺丰 Token 中转跳板平台 - 完整方案
# =========================================
# 架构：手机端 → 中继服务器 → 青龙脚本
# =========================================

## 一、架构说明

┌─────────────────┐     POST /api/update     ┌──────────────────┐     GET /api/cookie     ┌──────────────┐
│  手机端 (Stream) │ ──────────────────────→  │  中继跳板服务器   │ ←────────────────────── │  青龙定时脚本  │
│  抓取 sessionId  │                          │  Flask + SQLite   │                        │  顺丰.py      │
└─────────────────┘                          └──────────────────┘                        └──────────────┘
                                                     │
                                                     │ 定时检测（每6小时）
                                                     ▼
                                            ┌──────────────────┐
                                            │  Bark / PushPlus  │
                                            │  过期通知推送      │
                                            └──────────────────┘

## 二、部署中继服务器

### 方式一：直接运行（测试用）
```bash
cd /workspace
python3 sf_token_relay.py --port 5000
```

### 方式二：青龙面板运行（推荐）
1. 将 `sf_token_relay.py` 上传到青龙服务器
2. 创建定时任务：
   - 名称: 顺丰中继服务器
   - 命令: `cd /root && python3 sf_token_relay.py --port 5000 &`
   - 定时: 开机自启
3. 配置环境变量（可选）：
   - `SF_RELAY_TOKEN`: API 鉴权 Token
   - `SF_BARK_KEY`: Bark 推送 Key
   - `SF_PUSHPLUS_TOKEN`: PushPlus 推送 Token

### 方式三：使用 screen 后台运行
```bash
screen -S sf_relay
cd /workspace && python3 sf_token_relay.py
# Ctrl+A, D 分离
```

## 三、推送 Cookie（手机端操作）

### 方法1：Stream 抓包后命令行推送
```bash
# 在连接了中继服务器的机器上执行
bash sf_mobile_push.sh "_login_mobile_=138xxx; _login_user_id_=xxx; sessionId=xxx"
```

### 方法2：iOS 快捷指令
创建快捷指令，内容为：
```
获取剪贴板 → URL: http://服务器IP:5000/api/update
方法: POST
请求体: {"cookie": "剪贴板内容"}
```

### 方法3：curl 直接推送
```bash
curl -X POST http://服务器IP:5000/api/update \
  -H "Content-Type: application/json" \
  -d '{"cookie":"_login_mobile_=xxx; _login_user_id_=xxx; sessionId=xxx"}'
```

## 四、配置青龙脚本

### 环境变量设置
在青龙面板中设置以下环境变量：

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `SF_RELAY_URL` | 是 | 中继服务器地址，如 `http://192.168.1.100:5000` |
| `SF_RELAY_TOKEN` | 否 | API 鉴权 Token |
| `sfsyUrl` | 否 | 兼容旧模式，不填则自动使用中继 |

### 替换脚本
将修改后的 `顺丰.py` 上传到青龙，定时任务设为：
```
cron: 51 8,21 * * *
```

## 五、Cookie 续期流程（当收到过期通知时）

1. 打开手机 Stream，抓包顺丰小程序
2. 找到 `mcs-mimp-web.sf-express.com` 的请求
3. 复制完整 Cookie 字符串（含 sessionId）
4. 执行：
   ```bash
   curl -X POST http://中继服务器:5000/api/update \
     -H "Content-Type: application/json" \
     -d '{"cookie":"粘贴你抓到的完整cookie"}'
   ```
5. 确认返回 `"is_valid": true`

## 六、管理命令

```bash
# 查看状态
python3 sf_relay_manager.py status

# 推送新Cookie（交互式）
python3 sf_relay_manager.py update

# 检测所有账号有效性
python3 sf_relay_manager.py check

# 直接访问 Web 管理面板
# 浏览器打开 http://服务器IP:5000
```

## 七、Web 管理面板

访问 `http://服务器IP:5000` 可查看：
- 账号列表及状态
- 检测日志
- API 调用示例
- 系统配置信息

## 八、注意事项

1. ⚠️ 中继服务器不要暴露到公网，建议限制 IP 访问
2. ⚠️ 建议设置 `SF_RELAY_TOKEN` 环境变量开启 API 鉴权
3. ⚠️ 此方案仅用于个人学习研究
4. sessionId 有效期未知，建议每天检查一次有效性
5. 如果 sessionId 失效，会通过 Bark/PushPlus 推送通知