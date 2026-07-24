#!/bin/bash
set -e

RELAY_URL="${SF_RELAY_URL:-http://sf-relay:5000}"
RELAY_TOKEN="${SF_RELAY_TOKEN:-}"

echo "============================================"
echo "  顺丰 Cookie 登录器 (noVNC 模式)"
echo "  noVNC: http://localhost:${NOVNC_PORT}/vnc.html"
echo "  中继: ${RELAY_URL}"
echo "============================================"

# 1. 启动 Xvfb
echo "[1/4] 启动虚拟显示..."
Xvfb :99 -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x24 &
sleep 1

# 2. 启动 x11vnc
echo "[2/4] 启动 x11vnc..."
x11vnc -display :99 -forever -passwd sf123456 -shared -rfbport 5900 -nopw &
sleep 1

# 3. 启动 noVNC (websockify)
echo "[3/4] 启动 noVNC Web 界面..."
/opt/noVNC/utils/novnc_proxy --vnc localhost:5900 --listen ${NOVNC_PORT} &
sleep 1

# 4. 运行登录
echo "[4/4] 打开浏览器等待扫码登录..."
echo ">>> 请在浏览器打开 http://服务器IP:${NOVNC_PORT}/vnc.html"
echo ">>> 密码: sf123456"
echo ">>> 在弹出的页面中扫码登录顺丰"
echo ""

python3 sf_cookie_extractor.py --login

# 登录成功后尝试推送
if [ -f /app/sf_cookies.json ]; then
    echo ""
    echo "检测到 Cookie 已保存，尝试推送到中继..."
    python3 sf_cookie_extractor.py --once \
        --relay "${RELAY_URL}" \
        --token "${RELAY_TOKEN}"
    echo "登录完成！现在可以停止此容器，启动守护模式提取器。"
fi

echo "按 Ctrl+C 退出..."
wait
