# -*- coding: utf-8 -*-
"""
顺丰速运自动化 - QQ机器人插件
=============================
QL-Bot 业务项目插件，提供 QQ 交互逻辑。
配合 QL-SF 项目使用，QL-Bot 自动扫描 /opt/QL-SF/bot_plugins/ 加载。

命令列表:
  顺丰菜单    - 帮助菜单
  顺丰登录    - 设置 sfsyUrl，自动提交青龙
  顺丰状态    - 查看配置状态
  顺丰更新    - 手动更新 sfsyUrl / Cookie
  顺丰执行    - 手动执行全部任务
"""

import os
import re
import sys
import subprocess
import threading

from bot.plugins.base import Plugin
from bot.utils import Log
from bot.ql_api import ql
from bot.session import sessions

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SF_ENV_VARS = [
    ("sfsyUrl", "顺丰 sfsyUrl（抓包或扫码获取）"),
    ("SF_RELAY_URL", "中继服务器地址（可选，Docker方案启用）"),
    ("SF_RELAY_TOKEN", "中继鉴权Token（可选）"),
    ("SF_PROXY_API_URL", "代理API地址（可选）"),
]

MENU_TEXT = """📦 顺丰速运自动化
=============================
🎯 快捷: 顺丰执行 | 顺丰状态
🔑 顺丰登录 - 设置 sfsyUrl，自动提交青龙
📊 顺丰状态 - 查看 sfsyUrl 配置
🚀 顺丰执行 - 执行全部任务
📝 顺丰更新 [内容] - 手动更新 sfsyUrl 或 Cookie
=============================
sfsyUrl 获取:
  ① 顺丰APP绑定微信后，sm.linzixuan.work 扫码复制
  ② 小程序/APP-我的-积分，手动抓包 URL"""


class SFPlugin(Plugin):
    name = "SF-Express"
    commands = ["顺丰"]

    def __init__(self):
        super().__init__()
        self.project_dir = _PROJECT_DIR
        self._env_path = None

    def match(self, text):
        return text.strip().startswith("顺丰")

    def handle(self, text, sender_id, group_id=None):
        text = text.strip()
        if not text.startswith("顺丰"):
            return None

        rest = text[2:].strip()
        if not rest:
            return MENU_TEXT

        parts = rest.split(maxsplit=1)
        sub = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        if sub in ("菜单", "帮助", "help"):
            return MENU_TEXT
        if sub == "登录":
            return self._cmd_login(sender_id, group_id)
        if sub == "状态":
            return self._cmd_status(sender_id, group_id)
        if sub == "更新":
            return self._cmd_update(arg, sender_id, group_id)
        if sub in ("执行", "签到", "任务"):
            return self._cmd_run(sender_id, group_id)

        return MENU_TEXT

    # ---------- 环境文件 ----------
    def _get_env_path(self):
        if self._env_path:
            return self._env_path
        self._env_path = os.path.join(self.project_dir, ".env")
        return self._env_path

    def _read_env(self) -> dict:
        env = {}
        p = self._get_env_path()
        if not os.path.exists(p):
            self._init_env(p)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        env[k.strip()] = v.strip().strip("\"'")
        return env

    def _init_env(self, path: str):
        example = os.path.join(os.path.dirname(path), ".env.example")
        if os.path.exists(example):
            import shutil
            shutil.copy(example, path)
        else:
            self._write_env({})

    def _write_env(self, env: dict):
        p = self._get_env_path()
        lines = ["# 顺丰速运自动化 - 环境变量", ""]
        for key, desc in SF_ENV_VARS:
            val = env.get(key, "")
            lines.append(f"# {desc}")
            lines.append(f"{key}={val}")
            lines.append("")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ---------- 命令实现 ----------
    def _cmd_login(self, sender_id, group_id=None):
        sessions.set(sender_id, group_id, "sf_login", {})
        return (
            "🔑 请输入 sfsyUrl（支持两种方式）：\n"
            "方式1: 直接粘贴抓包得到的完整 URL\n"
            "方式2: 粘贴 Cookie 字符串 (_login_mobile_=xxx; sessionId=xxx)\n"
            "💡 获取: 顺丰APP-我的-积分抓包，或 sm.linzixuan.work 扫码"
        )

    def _login_session(self, sender_id, group_id, text, session):
        text = text.strip()
        data = session.get("data", {})

        if "url" not in data:
            data["url"] = text
            session["data"] = data

            # 尝试解析手机号
            phone = ""
            if "_login_mobile_" in text:
                m = re.search(r'_login_mobile_=([^;&\s]+)', text)
                if m:
                    phone = m.group(1)
            data["phone"] = phone

            env = self._read_env()
            env["sfsyUrl"] = text
            self._write_env(env)
            sessions.clear(sender_id, group_id)

            submit = self._auto_submit(env)
            phone_d = f"{phone[:3]}****{phone[-4:]}" if phone else "已保存"
            return (
                f"✅ 已保存！\n"
                f"📱 {phone_d}\n\n"
                f"{submit}"
            )
        return "⚠️ 请直接粘贴 sfsyUrl 或 Cookie"

    def _cmd_status(self, sender_id, group_id=None):
        env = self._read_env()
        url = env.get("sfsyUrl", "")

        if not url:
            return (
                "⚠️ 未配置 sfsyUrl\n"
                "请先执行 顺丰登录 进行设置"
            )

        # 脱敏显示
        if len(url) > 50:
            url_display = url[:30] + "..." + url[-10:]
        else:
            url_display = url[:20] + "..." if len(url) > 20 else url

        # 检测中继
        relay_url = env.get("SF_RELAY_URL", "")
        relay_status = ""
        if relay_url:
            relay_status = f"\n📡 中继: {relay_url}"

        return (
            f"📊 顺丰配置状态\n"
            f"📝 sfsyUrl: {url_display}"
            f"{relay_status}\n"
            f"💡 发送 顺丰执行 可手动运行"
        )

    def _cmd_update(self, arg, sender_id, group_id=None):
        if not arg:
            return (
                "📝 用法: 顺丰更新 [sfsyUrl 或 Cookie]\n"
                "例: 顺丰更新 https://mcs-mimp-web.sf-express.com/... \n"
                "或: 顺丰更新 _login_mobile_=138xxx; sessionId=xxx"
            )

        env = self._read_env()
        env["sfsyUrl"] = arg.strip()
        self._write_env(env)
        submit = self._auto_submit(env)

        phone = ""
        if "_login_mobile_" in arg:
            m = re.search(r'_login_mobile_=([^;&\s]+)', arg)
            if m:
                phone = m.group(1)
        phone_d = f"{phone[:3]}****{phone[-4:]}" if phone else "已更新"

        return (
            f"✅ 已更新！\n"
            f"📱 {phone_d}\n\n"
            f"{submit}"
        )

    def _cmd_run(self, sender_id, group_id=None):
        env = self._read_env()
        url = env.get("sfsyUrl", "")
        if not url:
            return "⚠️ 请先执行 顺丰登录 设置 sfsyUrl"

        script = os.path.join(self.project_dir, "顺丰.py")
        if not os.path.exists(script):
            return "❌ 脚本未找到: 顺丰.py"

        args = [sys.executable, script]

        def _bg():
            try:
                ec = os.environ.copy()
                ec.update(env)
                proc = subprocess.run(
                    args, cwd=self.project_dir, env=ec,
                    capture_output=True, text=True, timeout=300
                )
                Log.ok("SF 任务完成")
            except Exception as e:
                Log.error(f"SF 任务异常: {e}")

        threading.Thread(target=_bg, daemon=True).start()
        return "🚀 全部任务已提交，完成后查看青龙日志"

    def _auto_submit(self, env: dict) -> str:
        ql_url = env.get("QL_URL", "")
        ql_cid = env.get("QL_CLIENT_ID", "")
        ql_cs = env.get("QL_CLIENT_SECRET", "")
        if not ql_url or not ql_cid or not ql_cs:
            return (
                "⚠️ 青龙未配置\n"
                "请在 .env 中设置 QL_URL / QL_CLIENT_ID / QL_CLIENT_SECRET\n"
                "或在青龙面板手动添加环境变量 sfsyUrl"
            )

        try:
            ql.base_url = ql_url.rstrip("/")
            ql.client_id = ql_cid
            ql.client_secret = ql_cs
            ql.token = None

            ok = 0
            fail = 0
            for key, desc in SF_ENV_VARS:
                val = env.get(key, "")
                if not val:
                    continue
                try:
                    existing = ql.list_envs(search_value=key)
                    found = [e for e in existing if e.get("name") == key]
                    if found:
                        eid = found[0].get("id") or found[0].get("_id")
                        ql.update_env(eid, key, val, f"SF: {desc}")
                    else:
                        ql.create_env(key, val, f"SF: {desc}")
                    ok += 1
                except Exception:
                    fail += 1

            result = f"📤 青龙提交: ✅{ok}"
            if fail:
                result += f" ❌{fail}"
            result += (
                "\n定时任务:\n"
                " 任务名: SF-Express\n"
                " 命令: task 顺丰.py\n"
                " 定时: 10 12 * * *"
            )
            return result
        except Exception as e:
            return f"⚠️ 青龙提交失败: {e}"


def register_session_handlers(handlers: dict):
    handlers["sf_login"] = lambda text, sid, gid, sess: SFPlugin()._login_session(sid, gid, text, sess)
    Log.ok("SF-Express 已注册")
