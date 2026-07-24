#!/bin/bash
set -e

# ============================================================
#  顺丰全自动 Cookie 方案 - 一键部署脚本
#  适用: Debian 12 + Docker + 青龙面板
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()   { echo -e "${RED}[ERR]${NC} $1"; }

# ===================== 检查依赖 =====================
check_deps() {
    log_info "检查依赖..."

    if ! command -v docker &>/dev/null; then
        log_err "Docker 未安装"
        echo "  安装: curl -fsSL https://get.docker.com | sh"
        exit 1
    fi
    log_ok "Docker $(docker --version | grep -oP '\d+\.\d+\.\d+')"

    if ! docker compose version &>/dev/null; then
        log_err "Docker Compose 未安装"
        exit 1
    fi
    log_ok "Docker Compose $(docker compose version --short)"

    if ! docker info &>/dev/null; then
        log_err "Docker 守护进程未运行，请先启动 Docker"
        exit 1
    fi
    log_ok "Docker 守护进程运行中"

    # 检查端口冲突
    if ss -tlnp | grep -q ':5000 '; then
        log_warn "端口 5000 已被占用（中继服务器端口）"
    fi
    if ss -tlnp | grep -q ':6080 '; then
        log_warn "端口 6080 已被占用（noVNC 端口）"
    fi
}

# ===================== 检测青龙面板 =====================
detect_ql() {
    log_info "检测青龙面板..."

    # 方式1: docker 容器
    QL_CONTAINER=$(docker ps --format '{{.Names}}' | grep -iE 'qinglong|ql' | head -1)
    if [ -n "$QL_CONTAINER" ]; then
        QL_NETWORK=$(docker inspect "$QL_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' | awk '{print $1}')
        log_ok "检测到青龙面板容器: $QL_CONTAINER (网络: $QL_NETWORK)"
        return 0
    fi

    # 方式2: docker-compose
    for dir in /opt/qinglong /root/ql /home/*/qinglong /data/qinglong; do
        if [ -f "$dir/docker-compose.yml" ]; then
            log_ok "检测到青龙面板目录: $dir"
            QL_DIR="$dir"
            return 0
        fi
    done

    log_warn "未检测到青龙面板"
    log_info "如果青龙面板尚未安装，请先安装:"
    echo "  docker run -dit --name qinglong \\"
    echo "    -v /opt/qinglong:/ql \\"
    echo "    -p 5700:5700 \\"
    echo "    --restart always \\"
    echo "    whyour/qinglong:latest"
    return 0
}

# ===================== 准备文件 =====================
prepare_files() {
    log_info "准备部署文件..."

    # 复制脚本文件到构建上下文
    cp sf_token_relay.py docker/sf-relay/
    cp sf_cookie_extractor.py docker/sf-extractor/
    cp sf_cookie_extractor.py docker/sf-extractor/noVNC/

    log_ok "文件就绪"
}

# ===================== 配置环境变量 =====================
setup_env() {
    if [ -f .env ]; then
        log_info "已存在 .env 文件，跳过配置"
        return 0
    fi

    log_info "创建 .env 配置文件..."
    cat > .env << 'EOF'
# ============================================================
#  顺丰全自动方案 - 环境变量配置
# ============================================================

# 中继服务器 API 鉴权 Token（建议设置一个随机字符串）
SF_RELAY_TOKEN=你的随机Token

# Cookie 提取间隔（秒），默认 3600 = 1小时
EXTRACT_INTERVAL=3600

# 推送通知（至少配置一个）
# Bark 推送 (iOS): 在 App Store 下载 Bark，获取 Key
SF_BARK_KEY=
# PushPlus 推送 (通用): 在 https://www.pushplus.plus/ 获取 Token
SF_PUSHPLUS_TOKEN=
EOF

    # 生成随机 Token
    RANDOM_TOKEN=$(openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | xxd -p)
    if [ -n "$RANDOM_TOKEN" ]; then
        sed -i "s/你的随机Token/$RANDOM_TOKEN/" .env
        log_ok "已自动生成 API Token: $RANDOM_TOKEN"
    fi

    log_warn "请编辑 .env 文件，配置推送通知（可选但推荐）"
    echo "  vim $SCRIPT_DIR/.env"
}

# ===================== 处理青龙网络 =====================
setup_network() {
    # 如果检测到青龙网络，尝试让顺丰方案加入同一网络
    # 这样青龙脚本可以直接通过容器名访问中继
    if [ -n "$QL_NETWORK" ]; then
        # 检查 docker-compose.yml 中的网络配置
        if grep -q "external: true" docker-compose.yml 2>/dev/null; then
            log_info "已配置使用外部网络: $QL_NETWORK"
        else
            log_info "如需让青龙脚本通过容器名访问中继服务器，建议："
            echo ""
            echo "  方案1: 在 docker-compose.yml 的 networks 部分取消 external: true 注释"
            echo "         并将 sf-net 改名为 $QL_NETWORK"
            echo ""
            echo "  方案2: 手动将青龙容器加入 sf-network："
            echo "         docker network connect sf-network $QL_CONTAINER"
            echo ""
        fi
    fi
}

# ===================== 构建 =====================
build_images() {
    log_info "构建 Docker 镜像..."
    docker compose build --parallel
    log_ok "镜像构建完成"
}

# ===================== 首次登录引导 =====================
first_login_guide() {
    echo ""
    echo "============================================================"
    echo -e "${YELLOW}  首次登录引导${NC}"
    echo "============================================================"
    echo ""
    echo "你需要扫码登录一次，让浏览器保存登录态。有两种方式："
    echo ""
    echo -e "${GREEN}方式1: noVNC 远程桌面（推荐）${NC}"
    echo "  执行:  docker compose --profile login up sf-login"
    echo "  然后在浏览器打开: http://$(hostname -I | awk '{print $1}'):6080/vnc.html"
    echo "  在 noVNC 窗口中扫码登录顺丰"
    echo "  登录成功后按 Ctrl+C 停止容器"
    echo ""
    echo -e "${GREEN}方式2: 本地电脑登录后上传${NC}"
    echo "  1. 在本地电脑安装 Python + DrissionPage"
    echo "  2. 运行: python3 sf_cookie_extractor.py --login"
    echo "  3. 扫码登录成功后，打包 browser_data/ 目录"
    echo "  4. 上传到服务器的 Docker volume:"
    echo "     docker cp browser_data/. sf-extractor:/app/browser_data/"
    echo ""
}

# ===================== 启动服务 =====================
start_services() {
    log_info "启动中继服务器和 Cookie 提取器..."
    docker compose up -d sf-relay sf-extractor
    log_ok "服务启动完成"

    echo ""
    echo "============================================================"
    echo -e "${GREEN}  部署完成！${NC}"
    echo "============================================================"
    echo ""
    echo "  中继管理面板: http://$(hostname -I | awk '{print $1}'):5000"
    echo "  中继 API:     http://$(hostname -I | awk '{print $1}'):5000/api/cookie"
    echo ""

    # 检查服务状态
    sleep 3
    docker compose ps
}

# ===================== 配置青龙脚本 =====================
setup_qinglong() {
    echo ""
    echo "============================================================"
    echo -e "${BLUE}  配置青龙面板${NC}"
    echo "============================================================"
    echo ""
    echo "在青龙面板中完成以下配置："
    echo ""
    echo "  1. 添加环境变量:"
    echo "     名称: SF_RELAY_URL"
    echo "     值:   http://sf-relay:5000"
    echo "     (如果青龙和顺丰方案不在同一 Docker 网络)"
    echo "     (则使用: http://$(hostname -I | awk '{print $1}'):5000)"
    echo ""
    echo "  2. 添加环境变量:"
    echo "     名称: SF_RELAY_TOKEN"
    echo "     值:   $(grep SF_RELAY_TOKEN .env | cut -d= -f2)"
    echo ""
    echo "  3. 上传修改后的 顺丰.py 到青龙脚本目录"
    echo "  4. 添加定时任务:"
    echo "     cron: 51 8,21 * * *"
    echo ""
    echo "  5. （可选）如果青龙容器需要加入同一网络:"
    echo "     docker network connect sf-network $QL_CONTAINER"
    echo ""
}

# ===================== 主流程 =====================
main() {
    echo ""
    echo "============================================================"
    echo "  顺丰全自动 Cookie 方案 - Docker 部署"
    echo "============================================================"
    echo ""

    check_deps
    detect_ql
    prepare_files
    setup_env
    setup_network
    build_images
    start_services
    first_login_guide
    setup_qinglong

    echo "============================================================"
    log_ok "全部完成！"
    echo "============================================================"
}

main "$@"
