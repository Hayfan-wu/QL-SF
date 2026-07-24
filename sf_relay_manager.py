#!/usr/bin/env python3
"""
顺丰中继跳板 - 一键部署 & 运维脚本
=============================
用法:
  python3 sf_relay_manager.py status   查看状态
  python3 sf_relay_manager.py restart  重启中继
  python3 sf_relay_manager.py update   推送新Cookie（交互式）
  python3 sf_relay_manager.py check    检测所有账号有效性
"""

import json
import os
import sys
import requests

RELAY_URL = os.getenv('SF_RELAY_URL', 'http://localhost:5000')

def cmd_status():
    """查看中继服务器状态"""
    try:
        r = requests.get(f'{RELAY_URL}/api/accounts', timeout=5)
        data = r.json()
        if data.get('success'):
            accounts = data.get('data', [])
            print(f'📡 中继服务器: {RELAY_URL}')
            print(f'📋 账号数量: {len(accounts)}')
            for a in accounts:
                valid = '✅ 有效' if a.get('is_valid') else '❌ 失效'
                phone = a['phone'][:3] + '****' + a['phone'][7:] if len(a['phone']) >= 7 else a['phone']
                print(f'  [{a["id"]}] {phone} - {valid} (更新: {a["updated_at"]})')
        else:
            print(f'❌ 服务器异常: {data}')
    except Exception as e:
        print(f'❌ 连接失败: {e}')

def cmd_update():
    """交互式推送新Cookie"""
    print('📋 请输入从 Stream 抓到的完整 Cookie 字符串:')
    print('   格式: _login_mobile_=xxx; _login_user_id_=xxx; sessionId=xxx')
    cookie = input('> ').strip()
    if not cookie:
        print('❌ 未输入')
        return
    try:
        r = requests.post(f'{RELAY_URL}/api/update',
            json={'cookie': cookie}, timeout=10)
        data = r.json()
        if data.get('success'):
            valid = data['data'].get('is_valid', False)
            if valid:
                print('✅ 推送成功！Cookie 有效')
            else:
                print('⚠️ 已推送但 Cookie 无效（可能过期）')
            print(f'   测试结果: {json.dumps(data["data"]["test_result"], ensure_ascii=False)}')
        else:
            print(f'❌ 推送失败: {data}')
    except Exception as e:
        print(f'❌ 请求失败: {e}')

def cmd_check():
    """检测所有账号有效性"""
    try:
        r = requests.post(f'{RELAY_URL}/api/check/all', timeout=30)
        data = r.json()
        if data.get('success'):
            results = data.get('data', [])
            ok = sum(1 for x in results if x['is_valid'])
            fail = len(results) - ok
            print(f'📊 检测完成: {ok} 有效, {fail} 失效')
            for x in results:
                print(f'  {x["phone"]} - {"✅" if x["is_valid"] else "❌"}')
        else:
            print(f'❌ 检测失败: {data}')
    except Exception as e:
        print(f'❌ 请求失败: {e}')

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == 'status':
        cmd_status()
    elif cmd == 'update':
        cmd_update()
    elif cmd == 'check':
        cmd_check()
    elif cmd == 'restart':
        print('请手动重启中继服务器:')
        print('  1. 找到进程: ps aux | grep sf_token_relay')
        print('  2. 杀掉: kill <PID>')
        print('  3. 重启: python3 sf_token_relay.py &')
    else:
        print(f'未知命令: {cmd}')
        print(__doc__)

if __name__ == '__main__':
    main()