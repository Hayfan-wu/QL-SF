FROM python:3.11-slim

LABEL maintainer="sf-extractor"
WORKDIR /app

# 安装 Chromium 和必要依赖（DrissionPage 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    curl \
    xvfb \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/chromium /usr/bin/google-chrome

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sf_cookie_extractor.py .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 浏览器数据持久化目录
VOLUME /app/browser_data

# Xvfb 虚拟显示（无头服务器必备）
ENV DISPLAY=:99
ENV SCREEN_WIDTH=375
ENV SCREEN_HEIGHT=812

EXPOSE 9222

ENTRYPOINT ["/entrypoint.sh"]
