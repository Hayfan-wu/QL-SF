#!/bin/bash
set -e

MODE="${1:-daemon}"
RELAY_URL="${SF_RELAY_URL:-http://sf-relay:5000}"
RELAY_TOKEN="${SF_RELAY_TOKEN:-}"
INTERVAL="${EXTRACT_INTERVAL:-3600}"

echo "============================================"
echo "  顺丰 Cookie 自动提取器"
echo "  模式: ${MODE}"
echo "  中继: ${RELAY_URL}"
echo "  间隔: ${INTERVAL}s"
echo "============================================"

# 启动 Xvfb 虚拟显示（无图形界面的服务器必需）
echo "[*] 启动虚拟显示 Xvfb..."
Xvfb :99 -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x24 &
XVFB_PID=$!
sleep 1

# 清理函数
cleanup() {
    echo "[*] 正在停止..."
    kill $XVFB_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

case "$MODE" in
    login)
        echo "[*] 登录模式（需要 VNC 或 noVNC 连接扫码）"
        echo "[!] 注意: Docker 容器内无法直接显示浏览器"
        echo "[!] 如需扫码登录，请使用 noVNC 方案或手动上传 browser_data"
        python3 sf_cookie_extractor.py --login
        ;;
    once)
        echo "[*] 单次提取模式"
        python3 sf_cookie_extractor.py --once \
            --relay "${RELAY_URL}" \
            --token "${RELAY_TOKEN}"
        ;;
    daemon|"")
        echo "[*] 守护模式 - 每 ${INTERVAL} 秒提取一次"
        python3 sf_cookie_extractor.py --daemon \
            --relay "${RELAY_URL}" \
            --token "${RELAY_TOKEN}" \
            --interval "${INTERVAL}"
        ;;
    *)
        echo "未知模式: ${MODE}"
        echo "用法: docker exec <container> entrypoint.sh [login|once|daemon]"
        exit 1
        ;;
esac

cleanup
