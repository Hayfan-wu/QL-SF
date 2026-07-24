#!/usr/bin/env python3
"""
顺丰 Token 中转跳板平台
========================
功能：
  1. 存储和管理多个账号的 Cookie（sessionId）
  2. 提供 API 供青龙脚本拉取最新 Cookie
  3. 提供 Web 管理面板
  4. Cookie 有效性自动检测
  5. 过期提醒推送（Bark/PushPlus）

使用方式：
  python3 sf_token_relay.py [--port 5000]
"""

import hashlib
import json
import os
import sqlite3
import time
import urllib.parse
from datetime import datetime
from functools import wraps
from threading import Thread

import requests
from flask import Flask, jsonify, request, render_template_string, redirect
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ==================== 配置（可修改） ====================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sf_tokens.db')
RELAY_PORT = int(os.getenv('SF_RELAY_PORT', '5000'))
RELAY_TOKEN = os.getenv('SF_RELAY_TOKEN', '')  # 简单鉴权，留空则不校验
BARK_KEY = os.getenv('SF_BARK_KEY', '')  # Bark 推送 Key
PUSHPLUS_TOKEN = os.getenv('SF_PUSHPLUS_TOKEN', '')  # PushPlus 推送 Token

# 顺丰 API 配置
SF_BASE = 'https://mcs-mimp-web.sf-express.com/mcs-mimp'
SIGN_TOKEN = 'wwesldfs29aniversaryvdld29'
SYS_CODE = 'MCS-MIMP-CORE'

# ==================== 应用初始化 ====================
app = Flask(__name__)

# ==================== 数据库 ====================
def get_db():
    """获取数据库连接（线程安全）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            cookie_raw TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_valid_at TIMESTAMP,
            last_check_at TIMESTAMP,
            is_valid INTEGER DEFAULT 0,
            remark TEXT DEFAULT ''
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS check_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            result TEXT,
            detail TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()


# ==================== 签名工具 ====================
def generate_sign():
    timestamp = str(int(round(time.time() * 1000)))
    data = f'token={SIGN_TOKEN}&timestamp={timestamp}&sysCode={SYS_CODE}'
    signature = hashlib.md5(data.encode()).hexdigest()
    return {
        'sysCode': SYS_CODE,
        'timestamp': timestamp,
        'signature': signature
    }


# ==================== 鉴权装饰器 ====================
def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if RELAY_TOKEN:
            token = request.headers.get('X-Relay-Token', '')
            if token != RELAY_TOKEN:
                return jsonify({'success': False, 'error': 'Token 无效'}), 401
        return f(*args, **kwargs)
    return decorated


# ==================== 核心工具函数 ====================
def test_cookie_validity(phone, user_id, session_id):
    """测试一组 Cookie 是否有效，返回 (is_valid, obj_data)"""
    cookie_str = f"_login_mobile_={phone}; _login_user_id_={user_id}; sessionId={session_id}"
    headers = {
        'Host': 'mcs-mimp-web.sf-express.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'channel': 'wxwdsj',
        'platform': 'MINI_PROGRAM',
        'accept-language': 'zh-CN,zh;q=0.9',
        'Cookie': cookie_str,
    }
    sign_data = generate_sign()
    headers.update(sign_data)

    try:
        url = f'{SF_BASE}/commonPost/~memberNonactivity~integralTaskSignPlusService~automaticSignFetchPackage'
        resp = requests.post(url, headers=headers, json={}, timeout=15, verify=False)
        data = resp.json()
        if data.get('success') == True:
            return True, data.get('obj', {})
        else:
            err = data.get('errorMessage', '')
            return False, {'error': err}
    except Exception as e:
        return False, {'error': str(e)}


def send_notification(title, content):
    """发送推送通知（Bark / PushPlus）"""
    results = []
    if BARK_KEY:
        try:
            encoded = urllib.parse.quote(content)
            url = f'https://api.day.app/{BARK_KEY}/{urllib.parse.quote(title)}/{encoded}?group=SFToken'
            resp = requests.get(url, timeout=5)
            results.append(f'Bark: {"OK" if resp.status_code == 200 else resp.status_code}')
        except Exception as e:
            results.append(f'Bark: {str(e)}')
    if PUSHPLUS_TOKEN:
        try:
            url = 'https://www.pushplus.plus/send'
            resp = requests.post(url, json={
                'token': PUSHPLUS_TOKEN,
                'title': title,
                'content': content,
                'template': 'txt'
            }, timeout=5)
            results.append(f'PushPlus: {"OK" if resp.status_code == 200 else resp.status_code}')
        except Exception as e:
            results.append(f'PushPlus: {str(e)}')
    if not results:
        results.append('未配置推送渠道')
    return results


# ==================== API 路由 ====================

@app.route('/')
def index():
    """Web 管理面板首页"""
    conn = get_db()
    accounts = conn.execute('SELECT * FROM accounts ORDER BY id').fetchall()
    conn.close()
    return render_template_string(HTML_TEMPLATE, accounts=accounts, now=datetime.now())


@app.route('/api/accounts', methods=['GET'])
@require_token
def list_accounts():
    """获取所有账号列表"""
    conn = get_db()
    accounts = conn.execute('SELECT * FROM accounts ORDER BY id').fetchall()
    conn.close()
    return jsonify({
        'success': True,
        'data': [dict(a) for a in accounts]
    })


@app.route('/api/cookie', methods=['GET'])
@require_token
def get_cookie():
    """获取最新有效 Cookie 字符串（供脚本使用）"""
    conn = get_db()
    account = conn.execute(
        'SELECT * FROM accounts ORDER BY updated_at DESC LIMIT 1'
    ).fetchone()
    conn.close()

    if not account:
        return jsonify({'success': False, 'error': '没有存储的账号'}), 404

    cookie_str = f"_login_mobile_={account['phone']}; _login_user_id_={account['user_id']}; sessionId={account['session_id']}"
    return jsonify({
        'success': True,
        'data': {
            'id': account['id'],
            'phone': account['phone'],
            'cookie': cookie_str,
            'is_valid': bool(account['is_valid']),
            'updated_at': account['updated_at'],
        }
    })


@app.route('/api/cookie/<int:account_id>', methods=['GET'])
@require_token
def get_cookie_by_id(account_id):
    """获取指定账号的 Cookie 字符串"""
    conn = get_db()
    account = conn.execute('SELECT * FROM accounts WHERE id = ?', (account_id,)).fetchone()
    conn.close()
    if not account:
        return jsonify({'success': False, 'error': '账号不存在'}), 404
    cookie_str = f"_login_mobile_={account['phone']}; _login_user_id_={account['user_id']}; sessionId={account['session_id']}"
    return jsonify({
        'success': True,
        'data': {
            'id': account['id'],
            'phone': account['phone'],
            'cookie': cookie_str,
            'is_valid': bool(account['is_valid']),
            'updated_at': account['updated_at'],
        }
    })


@app.route('/api/update', methods=['POST'])
def update_token():
    """
    更新 Cookie（核心接口）
    JSON 参数:
      phone: 手机号
      user_id: 用户ID
      session_id: sessionId
      或直接传:
      cookie: 完整 cookie 字符串（自动解析）
    """
    data = request.get_json(silent=True) or {}
    phone = data.get('phone', '')
    user_id = data.get('user_id', '')
    session_id = data.get('session_id', '')

    # 支持直接传入完整 cookie 字符串
    cookie_raw = data.get('cookie', '')
    if cookie_raw:
        import re
        phone_m = re.search(r'_login_mobile_=([^;]+)', cookie_raw)
        uid_m = re.search(r'_login_user_id_=([^;]+)', cookie_raw)
        sid_m = re.search(r'sessionId=([^;]+)', cookie_raw)
        if phone_m: phone = phone_m.group(1)
        if uid_m: user_id = uid_m.group(1)
        if sid_m: session_id = sid_m.group(1)

    if not phone or not user_id or not session_id:
        return jsonify({'success': False, 'error': '缺少必填字段 phone/user_id/session_id'}), 400

    # 测试有效性
    is_valid, test_result = test_cookie_validity(phone, user_id, session_id)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()

    # 检查是否已存在该账号
    existing = conn.execute(
        'SELECT id FROM accounts WHERE user_id = ?', (user_id,)
    ).fetchone()

    if existing:
        conn.execute('''
            UPDATE accounts SET phone=?, session_id=?, cookie_raw=?,
            updated_at=CURRENT_TIMESTAMP, last_valid_at=?, last_check_at=CURRENT_TIMESTAMP,
            is_valid=?
            WHERE id=?
        ''', (phone, session_id, cookie_raw, now_str if is_valid else None, int(is_valid), existing['id']))
        account_id = existing['id']
    else:
        cursor = conn.execute('''
            INSERT INTO accounts (phone, user_id, session_id, cookie_raw,
            updated_at, last_valid_at, last_check_at, is_valid)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP, ?)
        ''', (phone, user_id, session_id, cookie_raw, now_str if is_valid else None, int(is_valid)))
        account_id = cursor.lastrowid

    # 记录检测日志
    conn.execute('''
        INSERT INTO check_logs (account_id, result, detail)
        VALUES (?, ?, ?)
    ''', (account_id, 'valid' if is_valid else 'invalid', json.dumps(test_result, ensure_ascii=False)))

    conn.commit()
    conn.close()

    # 推送通知
    status = '✅ 有效' if is_valid else '❌ 无效'
    masked_phone = phone[:3] + '****' + phone[7:] if len(phone) >= 7 else phone
    send_notification(
        f'顺丰 Token 更新 [{status}]',
        f'账号: {masked_phone}\n状态: {status}\n时间: {now_str}'
    )

    return jsonify({
        'success': True,
        'data': {
            'id': account_id,
            'phone': phone,
            'is_valid': is_valid,
            'test_result': test_result,
        }
    })


@app.route('/api/check/<int:account_id>', methods=['POST'])
@require_token
def check_token(account_id):
    """手动检测指定账号的 Cookie 有效性"""
    conn = get_db()
    account = conn.execute('SELECT * FROM accounts WHERE id = ?', (account_id,)).fetchone()
    if not account:
        conn.close()
        return jsonify({'success': False, 'error': '账号不存在'}), 404

    is_valid, test_result = test_cookie_validity(
        account['phone'], account['user_id'], account['session_id']
    )
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn.execute('''
        UPDATE accounts SET last_valid_at=?, last_check_at=CURRENT_TIMESTAMP, is_valid=?
        WHERE id=?
    ''', (now_str if is_valid else None, int(is_valid), account_id))

    conn.execute('''
        INSERT INTO check_logs (account_id, result, detail)
        VALUES (?, ?, ?)
    ''', (account_id, 'valid' if is_valid else 'invalid', json.dumps(test_result, ensure_ascii=False)))

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'id': account_id,
            'is_valid': is_valid,
            'result': test_result,
        }
    })


@app.route('/api/check/all', methods=['POST'])
@require_token
def check_all():
    """检测所有账号的有效性"""
    conn = get_db()
    accounts = conn.execute('SELECT * FROM accounts').fetchall()
    results = []
    for account in accounts:
        is_valid, test_result = test_cookie_validity(
            account['phone'], account['user_id'], account['session_id']
        )
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            UPDATE accounts SET last_valid_at=?, last_check_at=CURRENT_TIMESTAMP, is_valid=?
            WHERE id=?
        ''', (now_str if is_valid else None, int(is_valid), account['id']))
        conn.execute('''
            INSERT INTO check_logs (account_id, result, detail)
            VALUES (?, ?, ?)
        ''', (account['id'], 'valid' if is_valid else 'invalid', json.dumps(test_result, ensure_ascii=False)))
        results.append({
            'id': account['id'],
            'phone': account['phone'][:3] + '****' + account['phone'][7:] if len(account['phone']) >= 7 else account['phone'],
            'is_valid': is_valid,
        })
    conn.commit()
    conn.close()

    valid_count = sum(1 for r in results if r['is_valid'])
    invalid_count = len(results) - valid_count
    send_notification(
        '顺丰 Token 批量检测完成',
        f'共 {len(results)} 个账号\n有效: {valid_count}\n失效: {invalid_count}'
    )

    return jsonify({
        'success': True,
        'data': results,
    })


@app.route('/api/delete/<int:account_id>', methods=['DELETE'])
@require_token
def delete_account(account_id):
    """删除指定账号"""
    conn = get_db()
    conn.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
    conn.execute('DELETE FROM check_logs WHERE account_id = ?', (account_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/logs/<int:account_id>', methods=['GET'])
@require_token
def get_logs(account_id):
    """获取指定账号的检测日志"""
    conn = get_db()
    logs = conn.execute(
        'SELECT * FROM check_logs WHERE account_id = ? ORDER BY checked_at DESC LIMIT 50',
        (account_id,)
    ).fetchall()
    conn.close()
    return jsonify({
        'success': True,
        'data': [dict(l) for l in logs]
    })


# ==================== 定时检测任务 ====================
def periodic_check(interval_hours=6):
    """定时检测所有账号有效性，每 interval_hours 小时执行一次"""
    while True:
        time.sleep(interval_hours * 3600)
        try:
            conn = get_db()
            accounts = conn.execute('SELECT * FROM accounts').fetchall()
            for account in accounts:
                is_valid, _ = test_cookie_validity(
                    account['phone'], account['user_id'], account['session_id']
                )
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn.execute('''
                    UPDATE accounts SET last_valid_at=?, last_check_at=CURRENT_TIMESTAMP, is_valid=?
                    WHERE id=?
                ''', (now_str if is_valid else None, int(is_valid), account['id']))
                conn.execute('''
                    INSERT INTO check_logs (account_id, result, detail) VALUES (?, ?, ?)
                ''', (account['id'], 'valid' if is_valid else 'invalid', '定时检测'))

                # 如果失效，立刻推送通知
                if not is_valid:
                    masked = account['phone'][:3] + '****' + account['phone'][7:] if len(account['phone']) >= 7 else account['phone']
                    send_notification(
                        '⚠️ 顺丰 Token 已失效！',
                        f'账号: {masked}\n检测时间: {now_str}\n请尽快通过 Stream 抓取新的 sessionId 并更新'
                    )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f'定时检测异常: {e}')


# ==================== HTML 模板 ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>顺丰 Token 中转跳板</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; }
.header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; padding: 24px 32px; }
.header h1 { font-size: 24px; }
.header p { opacity: 0.85; margin-top: 6px; font-size: 14px; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 20px; margin-bottom: 20px; }
.card h2 { font-size: 18px; margin-bottom: 16px; color: #555; }
.api-section { background: #f8f9ff; border: 1px solid #e0e3ff; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.api-section h3 { font-size: 14px; color: #667eea; margin-bottom: 8px; }
.api-section code { display: block; background: #1e1e2e; color: #cdd6f4; padding: 12px; border-radius: 6px; font-size: 13px; margin: 8px 0; }
.api-section p { font-size: 13px; color: #666; margin: 4px 0; }
table { width: 100%; border-collapse: collapse; }
th { background: #f8f9fa; text-align: left; padding: 10px 12px; font-size: 13px; color: #666; font-weight: 600; }
td { padding: 10px 12px; font-size: 13px; border-top: 1px solid #eee; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge-ok { background: #d4edda; color: #155724; }
.badge-fail { background: #f8d7da; color: #721c24; }
.badge-pending { background: #fff3cd; color: #856404; }
.btn { display: inline-block; padding: 6px 14px; border-radius: 6px; text-decoration: none; font-size: 13px; border: none; cursor: pointer; }
.btn-primary { background: #667eea; color: #fff; }
.btn-danger { background: #dc3545; color: #fff; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.mt-2 { margin-top: 8px; }
.mb-2 { margin-bottom: 8px; }
.text-muted { color: #999; font-size: 12px; }
.footer { text-align: center; padding: 24px; color: #999; font-size: 12px; }
</style>
</head>
<body>
<div class="header">
    <h1>🚚 顺丰 Token 中转跳板</h1>
    <p>管理你的顺丰 Cookie，供青龙脚本自动拉取</p>
</div>
<div class="container">

    <div class="card">
        <h2>📌 快速使用</h2>
        <div class="api-section">
            <h3>1️⃣ 青龙脚本拉取 Cookie</h3>
            <code>curl -s http://你的服务器IP:5000/api/cookie | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['cookie'])"</code>
            <p>在 顺丰.py 脚本中设置环境变量 <strong>SF_RELAY_URL</strong> 即可自动拉取</p>
        </div>
        <div class="api-section">
            <h3>2️⃣ 手机端推送 Cookie（Stream 抓包后用）</h3>
            <code>curl -X POST http://你的服务器IP:5000/api/update \
  -H "Content-Type: application/json" \
  -d '{"cookie":"_login_mobile_=xxx; _login_user_id_=xxx; sessionId=xxx"}'</code>
            <p>支持完整 cookie 字符串自动解析</p>
        </div>
        <div class="api-section">
            <h3>3️⃣ 批量检测有效性</h3>
            <code>curl -X POST http://你的服务器IP:5000/api/check/all</code>
        </div>
    </div>

    <div class="card">
        <h2>📋 账号列表</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>手机号</th>
                    <th>用户ID</th>
                    <th>SessionID</th>
                    <th>状态</th>
                    <th>最后有效</th>
                    <th>更新时间</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                {% for a in accounts %}
                <tr>
                    <td>{{ a.id }}</td>
                    <td>{{ a.phone[:3] + '****' + a.phone[7:] if a.phone|length >= 7 else a.phone }}</td>
                    <td style="font-size:12px; max-width: 150px; overflow: hidden; text-overflow: ellipsis;">{{ a.user_id }}</td>
                    <td style="font-size:12px; max-width: 150px; overflow: hidden; text-overflow: ellipsis;">{{ a.session_id }}</td>
                    <td>
                        {% if a.is_valid == 1 %}
                        <span class="badge badge-ok">✅ 有效</span>
                        {% elif a.last_check_at %}
                        <span class="badge badge-fail">❌ 失效</span>
                        {% else %}
                        <span class="badge badge-pending">⏳ 未检测</span>
                        {% endif %}
                    </td>
                    <td class="text-muted">{{ a.last_valid_at or '-' }}</td>
                    <td class="text-muted">{{ a.updated_at }}</td>
                    <td>
                        <form action="/api/check/{{ a.id }}" method="POST" style="display:inline">
                            <button class="btn btn-primary btn-sm" type="submit">检测</button>
                        </form>
                        <form action="/api/delete/{{ a.id }}" method="POST" style="display:inline">
                            <button class="btn btn-danger btn-sm" type="submit">删除</button>
                        </form>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="8" style="text-align:center; color:#999; padding: 32px;">
                        📭 暂无账号数据，请通过 API 推送 Cookie
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="card">
        <h2>📝 最近检测日志</h2>
        <table>
            <thead>
                <tr>
                    <th>账号ID</th>
                    <th>结果</th>
                    <th>详情</th>
                    <th>检测时间</th>
                </tr>
            </thead>
            <tbody>
                {% set logs = [] %}
                {% for a in accounts %}
                    {% set conn = sqlite3.connect('sf_tokens.db') %}
                    {% set conn.row_factory = sqlite3.Row %}
                    {% set _logs = conn.execute('SELECT * FROM check_logs WHERE account_id = ? ORDER BY checked_at DESC LIMIT 5', (a.id,)).fetchall() %}
                    {% for l in _logs %}
                    <tr>
                        <td>{{ l.account_id }}</td>
                        <td>
                            {% if l.result == 'valid' %}
                            <span class="badge badge-ok">有效</span>
                            {% else %}
                            <span class="badge badge-fail">失效</span>
                            {% endif %}
                        </td>
                        <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; font-size: 12px;">{{ l.detail }}</td>
                        <td class="text-muted">{{ l.checked_at }}</td>
                    </tr>
                    {% endfor %}
                    {% set _ = conn.close() %}
                {% endfor %}
                {% if not accounts %}
                <tr><td colspan="4" style="text-align:center; color:#999;">暂无日志</td></tr>
                {% endif %}
            </tbody>
        </table>
    </div>

    <div class="card">
        <h2>⚙️ 系统信息</h2>
        <p class="text-muted">当前时间: {{ now.strftime('%Y-%m-%d %H:%M:%S') }}</p>
        <p class="text-muted">Bark 推送: {{ '已配置' if BARK_KEY else '未配置' }}</p>
        <p class="text-muted">PushPlus 推送: {{ '已配置' if PUSHPLUS_TOKEN else '未配置' }}</p>
        <p class="text-muted">API 鉴权: {{ '已开启' if RELAY_TOKEN else '未开启（建议开启）' }}</p>
    </div>

</div>
<div class="footer">
    顺丰 Token 中转跳板平台 · 仅用于个人学习研究
</div>
</body>
</html>
'''


# ==================== 启动 ====================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='顺丰 Token 中转跳板')
    parser.add_argument('--port', type=int, default=RELAY_PORT, help='监听端口')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址')
    parser.add_argument('--no-check', action='store_true', help='禁用定时检测')
    args = parser.parse_args()

    # 启动定时检测（每 6 小时）
    if not args.no_check:
        t = Thread(target=periodic_check, daemon=True, args=(6,))
        t.start()
        print('✅ 定时检测已启动（每 6 小时）')

    print(f'🌐 跳板服务器启动: http://{args.host}:{args.port}')
    print(f'📋 管理面板: http://localhost:{args.port}')
    print(f'🔑 API 鉴权: {"已开启" if RELAY_TOKEN else "未开启（建议设置 SF_RELAY_TOKEN 环境变量）"}')
    print(f'📱 Bark 推送: {"已配置" if BARK_KEY else "未配置"}')
    print(f'📱 PushPlus: {"已配置" if PUSHPLUS_TOKEN else "未配置"}')
    print('=' * 50)

    # 使用 Flask 内置服务器（开发用）
    # 生产环境建议用 gunicorn: gunicorn -w 2 -b 0.0.0.0:5000 sf_token_relay:app
    app.run(host=args.host, port=args.port, debug=False)

if __name__ == '__main__':
    main()