#!/usr/bin/env python3
"""
顺丰 Cookie 自动提取器
======================
原理：
  1. 使用 DrissionPage 控制浏览器打开顺丰 H5 网页
  2. 首次运行需要手动扫码登录（仅一次）
  3. 之后自动加载已保存的浏览器状态，免登录
  4. 定时从浏览器中提取 mcs-mimp-web.sf-express.com 的 Cookie
  5. 推送到中继服务器

依赖安装：
  pip install DrissionPage --break-system-packages

使用方式：
  # 首次运行（需要扫码）
  python3 sf_cookie_extractor.py --login
  
  # 后台自动提取（免登录，定时推送到中继）
  python3 sf_cookie_extractor.py --daemon --relay http://你的服务器:5000 --interval 3600
  
  # 仅提取一次并推送
  python3 sf_cookie_extractor.py --once --relay http://你的服务器:5000
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime

try:
    from DrissionPage import Chromium, ChromiumOptions, ChromiumPage
except ImportError:
    print("❌ 请先安装 DrissionPage: pip install DrissionPage --break-system-packages")
    sys.exit(1)

import requests

# ==================== 配置 ====================
BROWSER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'browser_data')
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sf_cookies.json')
TARGET_DOMAIN = 'mcs-mimp-web.sf-express.com'
TARGET_COOKIES = ['_login_mobile_', '_login_user_id_', 'sessionId']

# 顺丰 H5 网页（用于维持登录态）
SF_H5_URL = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/share/weChat/shareGiftReceiveRedirect'
SF_H5_INDEX = 'https://mcs-mimp-web.sf-express.com/pointLottery'


def create_browser():
    """创建带持久化用户数据的浏览器"""
    co = ChromiumOptions()
    co.set_user_data_path(BROWSER_DATA_DIR)
    co.set_local_port(9222)
    co.headless(False)  # 首次登录需要显示浏览器来扫码
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    # 模拟移动端 User-Agent（微信内置浏览器）
    co.set_user_agent(
        'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro Build/UQ1A.240205.002) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/122.0.6261.64 '
        'Mobile Safari/537.36 MicroMessenger/8.0.44.2501(0x28002C35)'
    )
    co.set_window_size(375, 812)  # iPhone 尺寸
    page = ChromiumPage(co)
    return page


def connect_browser(port=9222):
    """连接已运行的浏览器（调试模式）"""
    try:
        browser = Chromium(port)
        tab = browser.latest_tab
        return tab
    except Exception as e:
        print(f"⚠️ 连接浏览器失败: {e}")
        return None


def extract_cookies_from_browser(page):
    """从浏览器中提取顺丰目标 Cookie"""
    try:
        cookies = page.get_cookies(all_info=True)
    except Exception as e:
        print(f"⚠️ 获取 Cookie 失败: {e}")
        return None

    target = {}
    for c in cookies:
        domain = c.get('domain', '')
        name = c.get('name', '')
        # 匹配域名
        if TARGET_DOMAIN in domain and name in TARGET_COOKIES:
            target[name] = c.get('value', '')
            print(f"  📋 {name} = {c.get('value', '')[:20]}...")

    if len(target) == len(TARGET_COOKIES):
        return target
    else:
        missing = [k for k in TARGET_COOKIES if k not in target]
        print(f"  ⚠️ 缺少 Cookie: {missing}")
        return target if target else None


def push_to_relay(cookie_dict, relay_url, relay_token=''):
    """推送 Cookie 到中继服务器"""
    cookie_str = '; '.join(f'{k}={v}' for k, v in cookie_dict.items())
    
    headers = {'Content-Type': 'application/json'}
    if relay_token:
        headers['X-Relay-Token'] = relay_token
    
    try:
        resp = requests.post(
            f"{relay_url.rstrip('/')}/api/update",
            json={'cookie': cookie_str},
            headers=headers,
            timeout=15
        )
        data = resp.json()
        if data.get('success'):
            is_valid = data['data'].get('is_valid', False)
            print(f"  ✅ 推送成功，Cookie {'有效' if is_valid else '无效'}")
            return True
        else:
            print(f"  ❌ 推送失败: {data.get('error')}")
            return False
    except Exception as e:
        print(f"  ❌ 推送异常: {e}")
        return False


def save_cookies_local(cookie_dict):
    """保存 Cookie 到本地文件"""
    data = {
        'cookies': cookie_dict,
        'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  💾 Cookie 已保存到 {COOKIE_FILE}")


def do_login():
    """手动登录模式：打开浏览器让用户扫码"""
    print("=" * 50)
    print("🔐 顺丰 Cookie 自动提取器 - 登录模式")
    print("=" * 50)
    print()
    print("即将打开浏览器，请在弹出的页面中：")
    print("  1. 等待页面加载")
    print("  2. 如果跳转到微信登录页面，使用微信扫码登录")
    print("  3. 登录成功后，等待 5 秒自动提取 Cookie")
    print()
    
    input("按 Enter 键打开浏览器...")
    
    page = create_browser()
    print("🌐 正在打开顺丰 H5 页面...")
    page.get(SF_H5_URL)
    
    print("⏳ 等待页面加载和登录（最多 120 秒）...")
    print("💡 请在浏览器中完成微信扫码登录")
    
    # 等待用户完成登录（检测 sessionId 出现）
    for i in range(120):
        time.sleep(3)
        cookies = extract_cookies_from_browser(page)
        if cookies and 'sessionId' in cookies:
            print(f"\n✅ 检测到登录态！等待 5 秒确保 Cookie 完整...")
            time.sleep(5)
            cookies = extract_cookies_from_browser(page)
            if cookies and 'sessionId' in cookies:
                save_cookies_local(cookies)
                print(f"\n🎉 登录成功！Cookie 已提取并保存。")
                print(f"   手机号: {cookies.get('_login_mobile_', '未知')}")
                print(f"   用户ID: {cookies.get('_login_user_id_', '未知')[:20]}...")
                print(f"   SessionID: {cookies.get('sessionId', '未知')[:20]}...")
                print()
                print("后续运行将自动加载此登录态，无需重复扫码。")
                print("输入以下命令启动自动提取：")
                print(f"  python3 {os.path.basename(__file__)} --daemon --relay http://服务器:5000")
                break
        if i % 10 == 9:
            print(f"  ⏳ 已等待 {(i+1)*3} 秒...")
    else:
        print("❌ 超时未检测到登录态，请重试。")
    
    # 不关闭浏览器，保持登录态
    print("💡 浏览器保持打开状态，下次启动可直接复用。")


def do_extract(relay_url='', relay_token=''):
    """单次提取 Cookie 并推送"""
    print(f"🔍 正在提取 Cookie... ({datetime.now().strftime('%H:%M:%S')})")
    
    page = None
    
    # 尝试连接已运行的浏览器
    tab = connect_browser(9222)
    if tab:
        page = tab
        print("  📡 已连接运行中的浏览器")
    else:
        # 创建新浏览器（加载已保存的登录态）
        print("  🚀 启动浏览器...")
        page = create_browser()
        page.get(SF_H5_INDEX)
        time.sleep(3)
    
    cookies = extract_cookies_from_browser(page)
    
    if cookies and 'sessionId' in cookies:
        save_cookies_local(cookies)
        if relay_url:
            push_to_relay(cookies, relay_url, relay_token)
    else:
        print("  ❌ 未检测到有效 Cookie")
        print("  💡 可能需要重新登录，运行: python3 sf_cookie_extractor.py --login")
    
    return cookies


def do_daemon(relay_url, relay_token='', interval=3600):
    """守护进程模式：定时提取并推送"""
    print("=" * 50)
    print("🔄 顺丰 Cookie 自动提取器 - 守护模式")
    print("=" * 50)
    print(f"📡 中继服务器: {relay_url}")
    print(f"⏱️ 提取间隔: {interval} 秒 ({interval//3600} 小时)")
    print(f"🚀 首次提取...")
    print("=" * 50)
    
    fail_count = 0
    max_fail = 3
    
    while True:
        try:
            cookies = do_extract(relay_url, relay_token)
            if cookies and 'sessionId' in cookies:
                fail_count = 0
            else:
                fail_count += 1
                if fail_count >= max_fail:
                    print(f"\n❌ 连续 {max_fail} 次提取失败，可能需要重新登录。")
                    print("💡 请在服务器上运行: python3 sf_cookie_extractor.py --login")
                    # 不退出，继续尝试
                    fail_count = 0
        except Exception as e:
            print(f"  ❌ 异常: {e}")
        
        print(f"\n💤 下次提取: {interval} 秒后 ({datetime.now().strftime('%H:%M:%S')})")
        print("=" * 50)
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description='顺丰 Cookie 自动提取器')
    parser.add_argument('--login', action='store_true', help='手动登录模式（首次使用）')
    parser.add_argument('--once', action='store_true', help='提取一次 Cookie')
    parser.add_argument('--daemon', action='store_true', help='守护模式（定时提取）')
    parser.add_argument('--relay', type=str, default='', help='中继服务器地址')
    parser.add_argument('--token', type=str, default='', help='中继 API Token')
    parser.add_argument('--interval', type=int, default=3600, help='提取间隔秒数（默认1小时）')
    args = parser.parse_args()
    
    if args.login:
        do_login()
    elif args.daemon:
        if not args.relay:
            print("❌ 守护模式需要指定 --relay 参数")
            sys.exit(1)
        do_daemon(args.relay, args.token, args.interval)
    elif args.once:
        do_extract(args.relay, args.token)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
