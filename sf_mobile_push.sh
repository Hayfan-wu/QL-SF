#!/bin/bash
# ============================================================
# 顺丰手机端 - 推送 Cookie 到中继服务器
# 适用场景：Stream 抓包后，快速将 Cookie 推送到中继平台
# ============================================================
# 使用方法：
#   bash sf_mobile_push.sh <cookie完整字符串>
#
# 示例：
#   bash sf_mobile_push.sh "_login_mobile_=138xxx; _login_user_id_=xxx; sessionId=xxx"
# ============================================================

RELAY_URL="${SF_RELAY_URL:-http://你的服务器IP:5000}"

if [ $# -lt 1 ]; then
    echo "❌ 用法: $0 \"cookie字符串\""
    echo ""
    echo "示例:"
    echo "  $0 \"_login_mobile_=13856914746; _login_user_id_=8F3129A9490F4371A974D48ADEBE24F0; sessionId=10E75FBB7E54EBCD56530281ADCDDEF6\""
    exit 1
fi

COOKIE_STR="$1"

echo "📡 推送 Cookie 到中继服务器: $RELAY_URL"
echo "📋 Cookie: ${COOKIE_STR:0:50}..."

RESP=$(curl -s -X POST "$RELAY_URL/api/update" \
  -H "Content-Type: application/json" \
  -d "{\"cookie\": \"$COOKIE_STR\"}")

echo ""
echo "📡 响应:"
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"

SUCCESS=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('success') else 'false')" 2>/dev/null)
VALID=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('data',{}).get('is_valid') else 'false')" 2>/dev/null)

if [ "$SUCCESS" = "true" ] && [ "$VALID" = "true" ]; then
    echo "✅ 推送成功！Cookie 有效，可正常运行脚本。"
elif [ "$SUCCESS" = "true" ]; then
    echo "⚠️ 已推送但 Cookie 无效，请检查是否过期。"
else
    echo "❌ 推送失败，请检查中继服务器地址是否正确。"
fi