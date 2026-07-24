# -*- coding: utf-8 -*-
"""
顺丰全自动方案 - QL-Bot QQ机器人插件
=====================================
命令列表（中文）:
  /顺丰           - 查看当前Cookie状态
  /顺丰登录       - 启动noVNC扫码登录（发送链接到QQ）
  /顺丰更新       - 手动推送Cookie（从手机抓包后粘贴）
  /顺丰帮助       - 查看帮助

自动功能:
  Cookie失效时自动@管理员提醒
"""

import os
import re
import json
import time
import subprocess
import requests
from bot.plugins.base import Plugin

class SFPlugin(Plugin):
    name = 'sf'
    commands = [
        # 中文命令（主用）
        re.compile(r'^[/!]?顺丰帮助'),
        re.compile(r'^[/!]?顺丰登录'),
        re.compile(r'^[/!]?顺丰更新'),
        re.compile(r'^[/!]?顺丰状态'),
        re.compile(r'^[/!]?顺丰$'),
        # 英文命令（兼容保留）
        re.compile(r'^[/!]?(sf|顺丰)\b', re.IGNORECASE),
        re.compile(r'^[/!]?sf_login\b', re.IGNORECASE),
        re.compile(r'^[/!]?sf_update\b', re.IGNORECASE),
        re.compile(r'^[/!]?sf_help\b', re.IGNORECASE),
    ]

    RELAY_URL = 'http://127.0.0.1:5000'
    RELAY_TOKEN = ''
    LOGIN_PORT = 6080

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # QL-Bot 会自动传入 project_dir
        _fallback = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 如果本文件在 archive/ 子目录中，需再向上退一层到仓库根目录
        if os.path.basename(_fallback) == 'bot_plugins':
            _fallback = os.path.dirname(_fallback)
        self.project_dir = getattr(self, 'project_dir', _fallback)

        # 尝试从项目 .env 读取配置
        try:
            from bot.project_env import ProjectEnv
            env = ProjectEnv(self.project_dir)
            self.RELAY_URL = env.get('SF_RELAY_URL', 'http://127.0.0.1:5000')
            self.RELAY_TOKEN = env.get('SF_RELAY_TOKEN', '')
        except Exception as e:
            # 如果 QL-Bot 的 ProjectEnv 不可用，直接读取 .env
            env_path = os.path.join(self.project_dir, '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('SF_RELAY_URL='):
                            self.RELAY_URL = line.split('=', 1)[1].strip().strip('"').strip("'")
                        elif line.startswith('SF_RELAY_TOKEN='):
                            self.RELAY_TOKEN = line.split('=', 1)[1].strip().strip('"').strip("'")

        # 确定 docker compose 的 compose 文件路径
        self.compose_file = os.path.join(self.project_dir, 'docker-compose-simple.yml')
        if not os.path.exists(self.compose_file):
            # 尝试其他文件名
            alt = os.path.join(self.project_dir, 'docker-compose.yml')
            if os.path.exists(alt):
                self.compose_file = alt

    def _docker_cmd(self, *args):
        """构建 docker compose 命令"""
        cmd = ['docker', 'compose']
        if self.compose_file and os.path.exists(self.compose_file):
            cmd.extend(['-f', self.compose_file])
        cmd.extend(list(args))
        return cmd

    def _relay_get(self, path):
        headers = {}
        if self.RELAY_TOKEN:
            headers['X-Relay-Token'] = self.RELAY_TOKEN
        try:
            r = requests.get(f"{self.RELAY_URL}{path}", headers=headers, timeout=10)
            return r.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _relay_post(self, path, json_data=None):
        headers = {}
        if self.RELAY_TOKEN:
            headers['X-Relay-Token'] = self.RELAY_TOKEN
        try:
            r = requests.post(f"{self.RELAY_URL}{path}", headers=headers, json=json_data, timeout=15)
            return r.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle(self, text, sender_id, group_id=None):
        text = text.strip()
        lower = text.lower()

        # ========== 帮助 ==========
        if re.match(r'^[/!]?(顺丰帮助|sf_help)', lower):
            return self._help()

        # ========== 登录 ==========
        if re.match(r'^[/!]?(顺丰登录|sf_login)', lower):
            return self._start_login(sender_id)

        # ========== 手动更新Cookie ==========
        if re.match(r'^[/!]?(顺丰更新|sf_update)', lower):
            cookie = text.split(' ', 1)[1] if ' ' in text else ''
            return self._update_cookie(cookie)

        # ========== 状态查询（默认）==========
        return self._status()

    def _help(self):
        return (
            "[CQ:face,id=54] 顺丰全自动方案 帮助\n"
            "================================\n"
            "/顺丰          - 查看Cookie状态\n"
            "/顺丰登录      - 启动扫码登录（会发送noVNC链接）\n"
            "/顺丰更新      - 手动推送Cookie\n"
            "  例: /顺丰更新 _login_mobile_=138xxx; _login_user_id_=xxx; sessionId=xxx\n"
            "/顺丰帮助      - 查看本帮助\n"
            "================================\n"
            "首次使用请先执行 /顺丰登录 扫码登录"
        )

    def _status(self):
        data = self._relay_get('/api/accounts')
        if not data.get('success'):
            err = data.get('error', '未知错误')
            return f"[CQ:face,id=106] 中继服务器连接失败: {err}\n请先确认服务已启动: docker compose ps"

        accounts = data.get('data', [])
        if not accounts:
            return (
                "[CQ:face,id=106] 暂无账号数据\n"
                "请先执行 /顺丰登录 扫码登录，\n"
                "或执行 /顺丰更新 手动推送Cookie"
            )

        lines = ["[CQ:face,id=74] 顺丰Cookie状态"]
        for a in accounts:
            phone = a['phone'][:3] + '****' + a['phone'][7:] if len(a['phone']) >= 7 else a['phone']
            valid = "[CQ:face,id=74] 有效" if a.get('is_valid') else "[CQ:face,id=106] 失效"
            updated = a.get('updated_at', '-')
            lines.append(f"  [{a['id']}] {phone} - {valid}\n      更新: {updated}")
        return '\n'.join(lines)

    def _start_login(self, sender_id):
        """启动noVNC扫码登录"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            server_ip = s.getsockname()[0]
            s.close()
        except:
            server_ip = "你的服务器IP"

        # 检查noVNC是否已在运行
        try:
            r = requests.get(f"http://127.0.0.1:{self.LOGIN_PORT}/", timeout=2)
            if r.status_code == 200:
                return (
                    f"[CQ:face,id=74] 登录服务已在运行\n"
                    f"请在浏览器打开: http://{server_ip}:{self.LOGIN_PORT}/vnc.html\n"
                    f"密码: sf123456\n"
                    f"用手机微信扫码登录顺丰即可"
                )
        except:
            pass

        # 启动noVNC容器
        try:
            cmd = self._docker_cmd('--profile', 'login', 'up', '-d', 'sf-login')
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                cwd=self.project_dir
            )
            if result.returncode != 0:
                return f"[CQ:face,id=106] 启动登录服务失败:\n{result.stderr[:200]}"
        except Exception as e:
            return f"[CQ:face,id=106] 启动异常: {str(e)[:100]}"

        time.sleep(3)
        return (
            f"[CQ:face,id=74] 登录服务已启动！\n"
            f"================================\n"
            f"1. 在电脑浏览器打开:\n"
            f"   http://{server_ip}:{self.LOGIN_PORT}/vnc.html\n"
            f"2. 密码: sf123456\n"
            f"3. 在浏览器窗口中用手机微信扫码登录顺丰\n"
            f"4. 登录成功后Cookie会自动保存\n"
            f"================================\n"
            f"登录完成后发送 /顺丰 查看状态"
        )

    def _update_cookie(self, cookie_str):
        """手动推送Cookie"""
        if not cookie_str:
            return (
                "[CQ:face,id=106] 用法: /顺丰更新 [完整Cookie字符串]\n"
                "例: /顺丰更新 _login_mobile_=138xxx; _login_user_id_=xxx; sessionId=xxx"
            )

        data = self._relay_post('/api/update', {'cookie': cookie_str.strip()})
        if data.get('success'):
            is_valid = data['data'].get('is_valid', False)
            if is_valid:
                return "[CQ:face,id=74] Cookie推送成功！已验证有效。"
            else:
                return "[CQ:face,id=106] 已推送但Cookie验证无效，可能已过期。"
        else:
            err = data.get('error', '未知错误')
            return f"[CQ:face,id=106] 推送失败: {err}"


# ========== 会话处理器（如果需要多步交互）==========
def register_session_handlers(handlers):
    pass  # 本插件不需要多步会话
