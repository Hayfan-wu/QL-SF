#!/bin/bash
# ============================================================
#  顺丰全自动方案 - 一键安装脚本
#  适用: Debian 12 + 已有青龙面板
#  执行: curl -fsSL 你的链接/easy-install.sh | bash
# ============================================================

set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================"
echo "  顺丰全自动方案 - 一键安装"
echo "============================================"
echo ""

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请用 root 权限运行: sudo bash easy-install.sh${NC}"
    exit 1
fi

# 1. 安装Docker
echo "[1/6] 检查 Docker..."
if ! command -v docker &>/dev/null; then
    echo "  Docker 未安装，正在安装..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo -e "${GREEN}  Docker 安装完成${NC}"
else
    echo -e "${GREEN}  Docker 已安装${NC}"
fi

# 2. 创建项目目录
INSTALL_DIR="/opt/QL-SF"
echo "[2/6] 创建项目目录: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 3. 下载文件（假设文件已上传到服务器，实际使用git clone或curl）
echo "[3/6] 准备项目文件..."
# 如果当前目录已有文件，直接使用
if [ ! -f "docker-compose-simple.yml" ]; then
    echo -e "${YELLOW}  请将项目文件上传到 $INSTALL_DIR 后再运行${NC}"
    echo "  需要以下文件:"
    echo "    docker-compose-simple.yml"
    echo "    docker/ 目录（Dockerfile等）"
    echo "    sf_token_relay.py"
    echo "    sf_cookie_extractor.py"
    exit 1
fi

# 复制脚本到构建目录
cp sf_token_relay.py docker/sf-relay/
cp sf_cookie_extractor.py docker/sf-extractor/
cp sf_cookie_extractor.py docker/sf-extractor/noVNC/

echo -e "${GREEN}  文件准备完成${NC}"

# 4. 配置.env
echo "[4/6] 配置环境变量..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# 修改下面的Token（随便填一串字母数字）
SF_RELAY_TOKEN=ChangeMeToRandomString123

# Cookie刷新间隔（秒），默认1小时
EXTRACT_INTERVAL=3600

# 推送通知（可选）
SF_BARK_KEY=
SF_PUSHPLUS_TOKEN=
EOF
    echo -e "${YELLOW}  已创建 .env 文件，请编辑修改 Token${NC}"
    echo "  命令: nano $INSTALL_DIR/.env"
else
    echo -e "${GREEN}  .env 已存在，跳过${NC}"
fi

# 5. 构建并启动
echo "[5/6] 构建 Docker 镜像..."
docker compose -f docker-compose-simple.yml build --parallel
echo -e "${GREEN}  镜像构建完成${NC}"

echo "[6/6] 启动服务..."
docker compose -f docker-compose-simple.yml up -d
echo -e "${GREEN}  服务已启动${NC}"

# 获取IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "============================================"
echo -e "${GREEN}  安装完成！${NC}"
echo "============================================"
echo ""
echo "  中继面板: http://${SERVER_IP}:5000"
echo ""
echo "  接下来:"
echo "  1. 编辑 .env: nano $INSTALL_DIR/.env"
echo "  2. 重启服务: docker compose -f docker-compose-simple.yml restart"
echo "  3. 首次登录: docker compose -f docker-compose-simple.yml --profile login up -d sf-login"
echo "     然后浏览器打开 http://${SERVER_IP}:6080/vnc.html"
echo ""
echo "  查看日志:"
echo "    docker compose -f docker-compose-simple.yml logs -f"
echo ""
echo "============================================"
