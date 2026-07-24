# noVNC 容器 - 提供浏览器远程访问用于扫码登录
# 复用提取器的 Chromium 和 Xvfb，额外加 noVNC + websockify
FROM python:3.11-slim

LABEL maintainer="sf-novnc"
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    curl \
    xvfb \
    x11vnc \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/chromium /usr/bin/google-chrome

# 安装 noVNC 和 websockify
RUN wget -qO- https://github.com/novnc/noVNC/archive/refs/tags/v1.5.0.tar.gz | tar xz --strip-components=1 -C /opt/noVNC \
    && wget -qO /opt/noVNC/vnc.html https://raw.githubusercontent.com/novnc/noVNC/v1.5.0/vnc.html \
    && wget -qO- https://github.com/novnc/websockify/archive/refs/tags/v0.12.0.tar.gz | tar xz --strip-components=1 -C /opt/websockify \
    && pip install --no-cache-dir /opt/websockify

COPY requirements-extractor.txt .
RUN pip install --no-cache-dir -r requirements-extractor.txt

COPY sf_cookie_extractor.py .
COPY sf_login_gui.sh /app/sf_login_gui.sh
RUN chmod +x /app/sf_login_gui.sh

VOLUME /app/browser_data

ENV DISPLAY=:99
ENV SCREEN_WIDTH=375
ENV SCREEN_HEIGHT=812
ENV NOVNC_PORT=6080

EXPOSE 6080 9222

ENTRYPOINT ["/app/sf_login_gui.sh"]
