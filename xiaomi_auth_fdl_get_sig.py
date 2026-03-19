#!/usr/bin/env python3
"""
小米 FDL 自动化工具
支持扫码登录，自动保存凭证
只需输入设备 Token 和产品代号
"""

import sys
import os
import subprocess

# ==================== 依赖检查 ====================

def check_dependencies():
    """检查并安装必要的依赖"""
    missing = []
    
    # 检查 requests
    try:
        import requests
    except ImportError:
        missing.append(("requests", "requests"))
    
    # 检查 urllib3
    try:
        import urllib3
    except ImportError:
        missing.append(("urllib3", "urllib3"))
    
    # 检查 pycryptodome
    try:
        from Crypto.Cipher import AES
    except ImportError:
        missing.append(("pycryptodome", "pycryptodome"))
    
    if not missing:
        return True
    
    # 显示缺失的依赖
    print("╔" + "═" * 48 + "╗")
    print("║           依赖检查                             ║")
    print("╚" + "═" * 48 + "╝")
    print("\n检测到缺少以下依赖库：")
    for name, pkg in missing:
        print(f"  × {name}")
    
    # 检查 pip 是否可用
    pip_cmd = None
    for cmd in [sys.executable + " -m pip", "pip3", "pip", "python -m pip", "python3 -m pip"]:
        try:
            if " " in cmd:
                parts = cmd.split()
                result = subprocess.run(parts + ["--version"], capture_output=True, timeout=10)
            else:
                result = subprocess.run([cmd, "--version"], capture_output=True, timeout=10)
            if result.returncode == 0:
                pip_cmd = cmd
                break
        except:
            continue
    
    if not pip_cmd:
        print("\n× 未找到 pip 包管理器！")
        print("\n请手动安装 Python 和 pip：")
        print("  1. 下载 Python: https://www.python.org/downloads/")
        print("  2. 安装时勾选 'Add Python to PATH'")
        print("  3. 安装时勾选 'pip'")
        print("\n或者手动安装依赖：")
        print(f"  pip install {' '.join([pkg for _, pkg in missing])}")
        input("\n按 Enter 键退出...")
        return False
    
    # 询问是否自动安装
    print(f"\n检测到 pip: {pip_cmd}")
    choice = input("\n是否自动安装缺失的依赖？[Y/n]: ").strip().lower()
    
    if choice == 'n':
        print(f"\n请手动运行以下命令安装：")
        print(f"  {pip_cmd} install {' '.join([pkg for _, pkg in missing])}")
        input("\n按 Enter 键退出...")
        return False
    
    # 自动安装
    print("\n正在安装依赖...\n")
    for name, pkg in missing:
        print(f"  安装 {pkg}...")
        try:
            if " " in pip_cmd:
                parts = pip_cmd.split() + ["install", pkg]
                result = subprocess.run(parts, capture_output=True, text=True, timeout=120)
            else:
                result = subprocess.run([pip_cmd, "install", pkg], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                print(f"  √ {pkg} 安装成功")
            else:
                print(f"  × {pkg} 安装失败")
                print(f"    错误: {result.stderr[:200] if result.stderr else '未知错误'}")
                return False
        except subprocess.TimeoutExpired:
            print(f"  × {pkg} 安装超时")
            return False
        except Exception as e:
            print(f"  × {pkg} 安装出错: {e}")
            return False
    
    print("\n√ 所有依赖安装完成！")
    print("  请重新运行本程序。")
    input("\n按 Enter 键退出...")
    return False

# 首次运行检查依赖
if not check_dependencies():
    sys.exit(1)

# ==================== 导入模块 ====================

import requests
import json
import base64
import hashlib
import hmac
import random
import time
import gzip
import uuid
import urllib3
from urllib.parse import urlparse, parse_qs
from Crypto.Cipher import AES

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== 配置 ====================

IV_KEY = b"0102030405060708"
HMAC_SHA1_KEY = bytes.fromhex("327442656f45794a54756e6d57554771376251483241626e306b324e686875724f61714266797843754c56676e3441566a3773776361776535337544556e6f")
HMAC_SHA256_KEY = "B288B376D22C73E6BE8EA5AF36E5275E6FA67EDADF8B18F2E5D88ACA9A92E4A1"
MI_HOST = "https://unlock.update.miui.com"

# Token 保存路径
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "mi_fdl")
TOKEN_FILE = os.path.join(CONFIG_DIR, "token.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")

# ==================== 网络请求封装 ====================

class HttpClient:
    """HTTP 客户端，支持代理和重试"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.timeout = 30
        self.max_retries = 3
        self.proxy = "disabled"  # 默认禁用代理
        self.session.trust_env = False  # 默认不使用系统代理
        self.load_settings()
    
    def load_settings(self):
        """加载代理设置"""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.proxy = settings.get('proxy', 'disabled')
                    if self.proxy == 'disabled':
                        self.session.trust_env = False
                        self.session.proxies = {}
                    elif self.proxy:
                        self.session.trust_env = False
                        self.session.proxies = {
                            'http': self.proxy,
                            'https': self.proxy
                        }
                    else:
                        # proxy 为 None 表示使用系统代理
                        self.session.trust_env = True
                        self.session.proxies = {}
            except:
                pass
    
    def save_settings(self):
        """保存设置"""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        settings = {'proxy': self.proxy}
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    
    def set_proxy(self, proxy):
        """设置代理"""
        self.proxy = proxy
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
        else:
            self.session.proxies = {}
        self.save_settings()
    
    def disable_system_proxy(self):
        """禁用系统代理"""
        self.session.trust_env = False
        self.session.proxies = {}
        self.proxy = "disabled"
        self.save_settings()
    
    def enable_system_proxy(self):
        """启用系统代理"""
        self.session.trust_env = True
        self.session.proxies = {}
        self.proxy = None
        self.save_settings()
    
    def request(self, method, url, **kwargs):
        """发送请求，带重试"""
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('verify', False)
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                if method.upper() == 'GET':
                    return self.session.get(url, **kwargs)
                else:
                    return self.session.post(url, **kwargs)
            except requests.exceptions.ProxyError as e:
                last_error = e
                if attempt == 0:
                    print(f"\n  ! 代理连接失败，正在尝试直连...")
                    self.disable_system_proxy()
            except requests.exceptions.ConnectionError as e:
                last_error = e
                error_str = str(e).lower()
                if 'proxy' in error_str or 'tunnel' in error_str or 'remotedisconnected' in error_str:
                    if attempt == 0:
                        print(f"\n  ! 检测到代理问题，正在尝试直连...")
                        self.disable_system_proxy()
                else:
                    if attempt < self.max_retries - 1:
                        print(f"\n  ! 连接失败，第 {attempt + 2} 次重试...")
                        time.sleep(2)
            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    print(f"\n  ! 请求超时，第 {attempt + 2} 次重试...")
                    time.sleep(2)
            except Exception as e:
                last_error = e
                break
        
        raise last_error
    
    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)
    
    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

# 全局 HTTP 客户端
http = HttpClient()

# ==================== 加密函数 ====================

def aes_encrypt_raw(plaintext, key):
    cipher = AES.new(key, AES.MODE_CBC, IV_KEY)
    return cipher.encrypt(plaintext)

def aes_decrypt(ciphertext, key):
    cipher = AES.new(key, AES.MODE_CBC, IV_KEY)
    return cipher.decrypt(ciphertext)

def generate_random_string(length, lowercase=True):
    chars = "abcdef1234567890"
    result = ''.join(random.choice(chars) for _ in range(length))
    return result.lower() if lowercase else result

def get_hmac_sha1(content):
    return hmac.new(HMAC_SHA1_KEY, content.encode(), hashlib.sha1).hexdigest()

def get_sha1_hash(content):
    return hashlib.sha1(content.encode()).hexdigest()

def calculate_hmac_sha256(content):
    return hmac.new(HMAC_SHA256_KEY.encode(), content.encode(), hashlib.sha256).hexdigest()

def get_padding_hex(data_len):
    padding_map = [
        "10101010101010101010101010101010", "01", "0202", "030303", "04040404",
        "0505050505", "060606060606", "07070707070707", "0808080808080808",
        "090909090909090909", "0a0a0a0a0a0a0a0a0a0a", "0b0b0b0b0b0b0b0b0b0b0b",
        "0c0c0c0c0c0c0c0c0c0c0c0c", "0d0d0d0d0d0d0d0d0d0d0d0d0d",
        "0e0e0e0e0e0e0e0e0e0e0e0e0e0e", "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f",
        "10101010101010101010101010101010"
    ]
    padding_needed = (16 - (data_len % 16)) % 16
    if padding_needed == 0:
        padding_needed = 16
    return padding_map[padding_needed]

# ==================== Token 管理 ====================

def save_token(user_id, pass_token):
    """保存登录凭证"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "userId": str(user_id),
            "passToken": str(pass_token),
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  √ 登录凭证已保存到: {TOKEN_FILE}")
        return True
    except Exception as e:
        print(f"  × 保存凭证失败: {e}")
        return False

def load_token():
    """加载已保存的凭证"""
    if not os.path.exists(TOKEN_FILE):
        return None, None
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        user_id = data.get("userId")
        pass_token = data.get("passToken")
        if user_id and pass_token:
            return str(user_id), str(pass_token)
        return None, None
    except Exception as e:
        print(f"  ! 加载凭证出错: {e}")
        return None, None

def clear_token():
    """清除已保存的凭证"""
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
            print("  √ 登录凭证已清除")
    except Exception as e:
        print(f"  × 清除凭证失败: {e}")

# ==================== 扫码登录 ====================

class QRLogin:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    
    def get_login_params(self):
        """获取登录参数"""
        print("  正在获取登录参数...")
        url = "https://account.xiaomi.com/pass/serviceLogin"
        params = {"sid": "passport", "_json": "true"}
        
        response = self.session.get(url, params=params, headers=self.headers, timeout=30)
        text = response.text.replace("&&&START&&&", "")
        data = json.loads(text)
        
        return {
            "_sign": data.get("_sign", ""),
            "sid": data.get("sid", "passport"),
            "qs": data.get("qs", ""),
            "callback": data.get("callback", "https://account.xiaomi.com"),
            "serviceParam": data.get("serviceParam", '{"checkSafePhone":false}'),
            "_locale": "zh_CN"
        }
    
    def get_qr_ticket(self, login_params):
        """获取二维码"""
        print("  正在生成二维码...")
        
        lp_url = "https://account.xiaomi.com/longPolling/loginUrl"
        timestamp = int(time.time() * 1000)
        
        params = {
            "_qrsize": "180",
            "sid": login_params.get("sid", "passport"),
            "qs": login_params.get("qs", ""),
            "callback": login_params.get("callback", ""),
            "_sign": login_params.get("_sign", ""),
            "serviceParam": login_params.get("serviceParam", ""),
            "_locale": "zh_CN",
            "_hasLogo": "false",
            "_dc": str(timestamp),
        }
        
        headers = self.headers.copy()
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Referer"] = "https://account.xiaomi.com/"
        
        self.session.cookies.set("deviceId", f"wb_{uuid.uuid4()}", domain="account.xiaomi.com")
        self.session.cookies.set("pass_ua", "web", domain="account.xiaomi.com")
        
        response = self.session.get(lp_url, params=params, headers=headers, timeout=60)
        
        try:
            text = gzip.decompress(response.content).decode('utf-8')
        except:
            text = response.text
        
        if text.startswith("&&&START&&&"):
            text = text[11:]
        
        data = json.loads(text)
        
        if data.get("code") != 0:
            print(f"  × 获取二维码失败: {data.get('desc', '未知错误')}")
            return None
        
        qr_url = data.get("qr", "")
        lp_url = data.get("lp", "")
        ticket = None
        dc = "sgp"
        
        if qr_url:
            parsed = urlparse(qr_url)
            query = parse_qs(parsed.query)
            ticket = query.get("ticket", [""])[0]
            dc = query.get("dc", ["sgp"])[0]
        
        if not ticket and lp_url and "k=" in lp_url:
            ticket = lp_url.split("k=")[-1].split("&")[0]
        
        if not ticket:
            print("  × 无法获取二维码")
            return None
        
        return {
            "ticket": ticket,
            "dc": dc,
            "lp_url": lp_url or f"https://{dc}.lp.account.xiaomi.com/lp/s?k={ticket}",
            "qr_url": qr_url
        }
    
    def download_qrcode(self, qr_url, ticket, dc):
        """下载二维码图片"""
        if not qr_url:
            timestamp = int(time.time() * 1000)
            qr_url = f"https://account.xiaomi.com/pass/qr/login?ticket={ticket}&dc={dc}&sid=passport&_qrsize=180&ts={timestamp}"
        
        response = self.session.get(qr_url, headers=self.headers, timeout=30)
        
        os.makedirs(CONFIG_DIR, exist_ok=True)
        qr_file = os.path.join(CONFIG_DIR, "qrcode.png")
        
        with open(qr_file, 'wb') as f:
            f.write(response.content)
        
        try:
            if os.name == 'nt':
                os.startfile(qr_file)
            elif os.path.exists('/usr/bin/xdg-open'):
                os.system(f'xdg-open "{qr_file}" &')
        except:
            pass
        
        return qr_file
    
    def poll_login_status(self, ticket, lp_url, login_params):
        """等待扫码（支持二维码自动刷新）"""
        max_attempts = 40
        poll_interval = 3
        max_refresh = 5
        refresh_count = 0
        
        current_ticket = ticket
        current_lp_url = lp_url
        
        while refresh_count <= max_refresh:
            for attempt in range(max_attempts):
                status_chars = ['◐', '◓', '◑', '◒']
                elapsed = attempt * poll_interval
                qr_info = f"[第 {refresh_count + 1} 个二维码]" if refresh_count > 0 else ""
                print(f"\r  {status_chars[attempt % 4]} 等待扫码中... ({elapsed}秒) {qr_info}    ", end='', flush=True)
                
                try:
                    headers = self.headers.copy()
                    headers["X-Requested-With"] = "XMLHttpRequest"
                    
                    response = self.session.get(current_lp_url, headers=headers, timeout=poll_interval + 10)
                    
                    try:
                        text = gzip.decompress(response.content).decode('utf-8')
                    except:
                        text = response.text
                    
                    if text.startswith("&&&START&&&"):
                        text = text[11:]
                    
                    try:
                        data = json.loads(text)
                    except:
                        time.sleep(poll_interval)
                        continue
                    
                    code = data.get("code", -1)
                    
                    if code == 0 and data.get("location"):
                        print(f"\n  √ 扫码成功！")
                        return self.handle_login_success(data)
                    
                    elif code == 1:
                        print(f"\n  已扫码，请在手机上点击确认登录...")
                    
                    elif code == 2:
                        print(f"\n  ! 二维码已过期，正在自动刷新...")
                        break
                    
                    elif code == 3:
                        print(f"\n  × 您在手机上取消了登录")
                        return None
                    
                    if data.get("loginUrl") or data.get("location"):
                        print(f"\n  √ 登录成功！")
                        return self.handle_login_success(data)
                    
                    time.sleep(poll_interval)
                    
                except KeyboardInterrupt:
                    print(f"\n  × 已取消")
                    return None
                except requests.exceptions.Timeout:
                    continue
                except:
                    time.sleep(poll_interval)
                    continue
            else:
                print(f"\n  ! 等待超时，正在刷新二维码...")
            
            refresh_count += 1
            if refresh_count > max_refresh:
                print(f"\n  × 二维码刷新次数已达上限（{max_refresh}次）")
                return None
            
            qr_info = self.get_qr_ticket(login_params)
            if not qr_info:
                print(f"  × 刷新二维码失败")
                return None
            
            current_ticket = qr_info["ticket"]
            current_lp_url = qr_info["lp_url"]
            
            qr_file = self.download_qrcode(
                qr_info.get("qr_url"),
                current_ticket,
                qr_info.get("dc", "sgp")
            )
            print(f"  √ 新二维码已生成，请重新扫码\n")
        
        print(f"\n  × 登录失败")
        return None
    
    def handle_login_success(self, data):
        """处理登录成功"""
        login_url = data.get("location", data.get("loginUrl", ""))
        
        if login_url:
            response = self.session.get(login_url, headers=self.headers, allow_redirects=True, timeout=30)
            cookies = {c.name: c.value for c in self.session.cookies}
            
            pass_token = cookies.get("passToken")
            user_id = cookies.get("userId", "")
            
            if pass_token and user_id:
                return {"userId": user_id, "passToken": pass_token}
        
        pass_token = data.get("passToken")
        user_id = str(data.get("userId", ""))
        
        if pass_token and user_id:
            return {"userId": user_id, "passToken": pass_token}
        
        return None
    
    def login(self):
        """执行扫码登录"""
        print("\n【扫码登录】")
        
        try:
            login_params = self.get_login_params()
            qr_info = self.get_qr_ticket(login_params)
            
            if not qr_info:
                return None
            
            qr_file = self.download_qrcode(
                qr_info.get("qr_url"),
                qr_info["ticket"],
                qr_info.get("dc", "sgp")
            )
            
            print(f"\n  二维码图片: {qr_file}")
            print("  ┌────────────────────────────────────────┐")
            print("  │   请使用以下 App 扫描二维码登录：      │")
            print("  │   • 小米手机（设置-小米账号）          │")
            print("  │   • 米家 App                           │")
            print("  │   • 小米商城 App                       │")
            print("  └────────────────────────────────────────┘\n")
            
            result = self.poll_login_status(
                qr_info["ticket"],
                qr_info["lp_url"],
                login_params
            )
            
            if result:
                print(f"  账号 ID: {result['userId']}")
                save_token(result['userId'], result['passToken'])
                return result
            
            return None
            
        except Exception as e:
            print(f"  × 登录出错: {e}")
            return None

# ==================== FDL 请求函数 ====================

def login_and_get_credentials(user_id, pass_token):
    """获取解锁服务凭证"""
    print("\n【步骤 1/4】验证账号...")
    
    try:
        device_id = f'wb_{generate_random_string(36, False)}'
        url = 'https://account.xiaomi.com/pass/serviceLogin?sid=unlockApi&_json=true&passive=true&hidden=false'
        
        response = http.get(url, cookies={
            'passToken': pass_token,
            'userId': user_id,
            'deviceId': device_id
        }, headers={
            'User-Agent': 'MITUNES',
            'Content-Type': 'application/x-www-form-urlencoded'
        })
        
        result = json.loads(response.text.replace('&&&START&&&', ''))
        
        if result.get('code') != 0 or not result.get('ssecurity'):
            print(f"  × 验证失败: {result.get('description', '未知错误')}")
            return None
        
        ssecurity = result.get('ssecurity')
        location = result.get('location')
        print(f"  √ 账号验证成功")
        
        print("\n【步骤 2/4】获取服务令牌...")
        response = http.get(location, headers={
            'User-Agent': 'MITUNES',
            'Accept': '*/*'
        }, allow_redirects=True)
        
        service_token = None
        unlock_api_ph = None
        
        for cookie in response.cookies:
            if cookie.name == 'serviceToken':
                service_token = cookie.value
            elif cookie.name == 'unlockApi_ph':
                unlock_api_ph = cookie.value
        
        if not service_token:
            print("  × 获取服务令牌失败")
            return None
        
        print(f"  √ 服务令牌获取成功")
        
        return {
            'user_id': str(result.get('userId')),
            'ssecurity': ssecurity,
            'service_token': service_token,
            'unlock_api_ph': unlock_api_ph,
            'skey': base64.b64decode(ssecurity)
        }
    
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if 'proxy' in error_msg.lower() or 'tunnel' in error_msg.lower():
            print(f"  × 网络连接失败（代理问题）")
            print(f"    提示: 请检查代理设置或在主菜单选择「网络设置」")
        else:
            print(f"  × 网络连接失败: {error_msg[:100]}")
        return None
    except Exception as e:
        print(f"  × 出错: {e}")
        return None

def get_nonce(creds):
    """获取请求随机数"""
    print("\n【步骤 3/4】获取请求随机数...")
    
    try:
        rasli = generate_random_string(16, True)
        skey = creds['skey']
        ssecurity = creds['ssecurity']
        
        r_hex = rasli.encode().hex() + "10101010101010101010101010101010"
        r_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(r_hex), skey)).decode()
        
        sid_hex = "miui_unlocktool_client".encode().hex() + "0a0a0a0a0a0a0a0a0a0a"
        sid_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sid_hex), skey)).decode()
        
        sign_content = f"POST\n/api/v2/nonce\nr={rasli}&sid=miui_unlocktool_client"
        sign_hmac = get_hmac_sha1(sign_content)
        sign_hex = sign_hmac.encode().hex() + "0808080808080808"
        sign_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sign_hex), skey)).decode()
        
        sig_content = f"POST&/api/v2/nonce&r={r_encrypted}&sid={sid_encrypted}&sign={sign_encrypted}&{ssecurity}"
        signature = base64.b64encode(bytes.fromhex(get_sha1_hash(sig_content))).decode()
        
        response = http.post(f"{MI_HOST}/api/v2/nonce", data={
            'r': r_encrypted,
            'sid': sid_encrypted,
            'sign': sign_encrypted,
            'signature': signature
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'XiaomiPCSuite',
            'Cookie': f"serviceToken={creds['service_token']};userId={creds['user_id']};unlockApi_slh=null;unlockApi_ph={creds['unlock_api_ph']}"
        })
        
        encrypted_data = base64.b64decode(response.text.replace('&&&START&&&', ''))
        decrypted = aes_decrypt(encrypted_data, skey)
        result = json.loads(base64.b64decode(decrypted[:-8]).decode())
        
        if result.get('code') == 0:
            print(f"  √ 随机数获取成功")
            return result.get('nonce')
        else:
            print(f"  × 获取失败: {result.get('description')}")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"  × 网络连接失败")
        return None
    except Exception as e:
        print(f"  × 出错: {e}")
        return None

def send_fdl(creds, nonce, device_token, product_name):
    """发送 FDL 授权请求"""
    print("\n【步骤 4/4】发送 FDL 授权请求...")
    
    try:
        skey = creds['skey']
        ssecurity = creds['ssecurity']
        user_id = creds['user_id']
        
        request_data = json.dumps({
            "clientId": "2",
            "clientVersion": "6.6.816.30",
            "deviceInfo": {"boardVersion": "", "deviceName": "", "product": product_name, "socId": ""},
            "deviceToken": device_token,
            "language": "en",
            "operate": "unlock",
            "pcId": generate_random_string(32, False),
            "region": "",
            "uid": user_id
        }, separators=(',', ':'))
        
        data64 = base64.b64encode(request_data.encode()).decode()
        
        app_id_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("31" + "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f"), skey)).decode()
        sid_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("miui_unlocktool_client".encode().hex() + "0a0a0a0a0a0a0a0a0a0a"), skey)).decode()
        
        data_hex = data64.encode().hex()
        data_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(data_hex + get_padding_hex(len(data_hex) // 2)), skey)).decode()
        
        nonce_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(nonce.encode().hex() + "0808080808080808"), skey)).decode()
        
        sha256_raw = calculate_hmac_sha256(data64)
        sha_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sha256_raw.encode().hex() + "10101010101010101010101010101010"), skey)).decode()
        
        sign_content = f"POST\n/api/v2/fastboot2edl\nappId=1&data={data64}&sha={sha256_raw}&nonce={nonce}&sid=miui_unlocktool_client"
        sign_hmac = get_hmac_sha1(sign_content)
        sign_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sign_hmac.encode().hex() + "0808080808080808"), skey)).decode()
        
        sig_content = f"POST&/api/v2/fastboot2edl&appId={app_id_encrypted}&data={data_encrypted}&nonce={nonce_encrypted}&sha={sha_encrypted}&sid={sid_encrypted}&sign={sign_encrypted}&{ssecurity}"
        signature = base64.b64encode(bytes.fromhex(get_sha1_hash(sig_content))).decode()
        
        response = http.post(f"{MI_HOST}/api/v2/fastboot2edl", data={
            'sid': sid_encrypted,
            'data': data_encrypted,
            'appId': app_id_encrypted,
            'nonce': nonce_encrypted,
            'sha': sha_encrypted,
            'sign': sign_encrypted,
            'signature': signature
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'XiaomiPCSuite',
            'Cookie': f"serviceToken={creds['service_token']};userId={user_id};unlockApi_slh=null;unlockApi_ph={creds['unlock_api_ph']}"
        })
        
        encrypted_data = base64.b64decode(response.text.replace('&&&START&&&', ''))
        decrypted = aes_decrypt(encrypted_data, skey)
        json_str = base64.b64decode(decrypted).decode(errors='ignore')
        json_str = json_str.rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
        
        return json.loads(json_str)
    
    except requests.exceptions.RequestException as e:
        print(f"  × 网络连接失败")
        return {"code": -1, "descEN": "网络连接失败"}
    except Exception as e:
        print(f"  × 出错: {e}")
        return {"code": -1, "descEN": str(e)}

def send_unlock(creds, nonce, device_token, product_name):
    """发送 Bootloader 解锁请求"""
    print("\n【步骤 4/4】发送 Bootloader 解锁请求...")
    
    try:
        skey = creds['skey']
        ssecurity = creds['ssecurity']
        user_id = creds['user_id']
        
        request_data = json.dumps({
            "clientId": "2",
            "clientVersion": "7.6.727.43",
            "deviceInfo": {"boardVersion": "", "deviceName": "", "product": product_name, "socId": ""},
            "deviceToken": device_token,
            "language": "en",
            "operate": "unlock",
            "pcId": generate_random_string(32, False),
            "region": "",
            "uid": user_id
        }, separators=(',', ':'))
        
        data64 = base64.b64encode(request_data.encode()).decode()
        
        app_id_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("31" + "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f"), skey)).decode()
        sid_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("miui_unlocktool_client".encode().hex() + "0a0a0a0a0a0a0a0a0a0a"), skey)).decode()
        
        data_hex = data64.encode().hex()
        data_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(data_hex + get_padding_hex(len(data_hex) // 2)), skey)).decode()
        
        nonce_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(nonce.encode().hex() + "0808080808080808"), skey)).decode()
        
        sha256_raw = calculate_hmac_sha256(data64)
        sha_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sha256_raw.encode().hex() + "10101010101010101010101010101010"), skey)).decode()
        
        sign_content = f"POST\n/api/v3/ahaUnlock\nappId=1&data={data64}&sha={sha256_raw}&nonce={nonce}&sid=miui_unlocktool_client"
        sign_hmac = get_hmac_sha1(sign_content)
        sign_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sign_hmac.encode().hex() + "0808080808080808"), skey)).decode()
        
        sig_content = f"POST&/api/v3/ahaUnlock&appId={app_id_encrypted}&data={data_encrypted}&nonce={nonce_encrypted}&sha={sha_encrypted}&sid={sid_encrypted}&sign={sign_encrypted}&{ssecurity}"
        signature = base64.b64encode(bytes.fromhex(get_sha1_hash(sig_content))).decode()
        
        response = http.post(f"{MI_HOST}/api/v3/ahaUnlock", data={
            'sid': sid_encrypted,
            'data': data_encrypted,
            'appId': app_id_encrypted,
            'nonce': nonce_encrypted,
            'sha': sha_encrypted,
            'sign': sign_encrypted,
            'signature': signature
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'XiaomiPCSuite',
            'Cookie': f"serviceToken={creds['service_token']};userId={user_id};unlockApi_slh=null;unlockApi_ph={creds['unlock_api_ph']}"
        })
        
        encrypted_data = base64.b64decode(response.text.replace('&&&START&&&', ''))
        decrypted = aes_decrypt(encrypted_data, skey)
        json_str = base64.b64decode(decrypted).decode(errors='ignore')
        json_str = json_str.rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
        
        return json.loads(json_str)
    
    except requests.exceptions.RequestException as e:
        print(f"  × 网络连接失败")
        return {"code": -1, "descEN": "网络连接失败"}
    except Exception as e:
        print(f"  × 出错: {e}")
        return {"code": -1, "descEN": str(e)}

def send_flash(creds, nonce, flash_token):
    """发送 Flash 授权请求"""
    print("\n【步骤 4/4】发送 Flash 授权请求...")
    
    try:
        skey = creds['skey']
        ssecurity = creds['ssecurity']
        user_id = creds['user_id']
        
        request_data = json.dumps({
            "clientId": "mtkFlash",
            "clientVersion": "6.3.706.22",
            "flashToken": base64.b64encode(flash_token.encode()).decode(),
            "pcId": generate_random_string(32, False)
        }, separators=(',', ':'))
        
        data64 = base64.b64encode(request_data.encode()).decode()
        
        app_id_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("31" + "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f"), skey)).decode()
        sid_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("miui_unlocktool_client".encode().hex() + "0a0a0a0a0a0a0a0a0a0a"), skey)).decode()
        
        data_hex = data64.encode().hex()
        data_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(data_hex + get_padding_hex(len(data_hex) // 2)), skey)).decode()
        
        nonce_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(nonce.encode().hex() + "0808080808080808"), skey)).decode()
        
        sha256_raw = calculate_hmac_sha256(data64)
        sha_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sha256_raw.encode().hex() + "10101010101010101010101010101010"), skey)).decode()
        
        sign_content = f"POST\n/api/v1/flash/ahaFlash\nappId=1&data={data64}&sha={sha256_raw}&nonce={nonce}&sid=miui_unlocktool_client"
        sign_hmac = get_hmac_sha1(sign_content)
        sign_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sign_hmac.encode().hex() + "0808080808080808"), skey)).decode()
        
        sig_content = f"POST&/api/v1/flash/ahaFlash&appId={app_id_encrypted}&data={data_encrypted}&nonce={nonce_encrypted}&sha={sha_encrypted}&sid={sid_encrypted}&sign={sign_encrypted}&{ssecurity}"
        signature = base64.b64encode(bytes.fromhex(get_sha1_hash(sig_content))).decode()
        
        response = http.post(f"{MI_HOST}/api/v1/flash/ahaFlash", data={
            'sid': sid_encrypted,
            'data': data_encrypted,
            'appId': app_id_encrypted,
            'nonce': nonce_encrypted,
            'sha': sha_encrypted,
            'sign': sign_encrypted,
            'signature': signature
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'XiaomiPCSuite',
            'Cookie': f"serviceToken={creds['service_token']};userId={user_id};unlockApi_slh=null;unlockApi_ph={creds['unlock_api_ph']}"
        })
        
        encrypted_data = base64.b64decode(response.text.replace('&&&START&&&', ''))
        decrypted = aes_decrypt(encrypted_data, skey)
        json_str = base64.b64decode(decrypted).decode(errors='ignore')
        json_str = json_str.rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
        
        return json.loads(json_str)
    
    except requests.exceptions.RequestException as e:
        print(f"  × 网络连接失败")
        return {"code": -1, "descEN": "网络连接失败"}
    except Exception as e:
        print(f"  × 出错: {e}")
        return {"code": -1, "descEN": str(e)}

def send_erase_frp(creds, nonce, device_token, product_name, device_name=""):
    """发送擦除 FRP 请求"""
    print("\n【步骤 4/4】发送擦除 FRP 请求...")
    
    try:
        skey = creds['skey']
        ssecurity = creds['ssecurity']
        user_id = creds['user_id']
        
        request_data = json.dumps({
            "clientId": "2",
            "clientVersion": "1.1.505.53",
            "deviceInfo": {"deviceName": device_name, "product": product_name},
            "deviceToken": device_token,
            "language": "en",
            "operate": "erasefrp",
            "pcId": generate_random_string(32, False),
            "region": "",
            "uid": user_id
        }, separators=(',', ':'))
        
        data64 = base64.b64encode(request_data.encode()).decode()
        
        app_id_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("31" + "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f"), skey)).decode()
        sid_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("miui_unlocktool_client".encode().hex() + "0a0a0a0a0a0a0a0a0a0a"), skey)).decode()
        
        data_hex = data64.encode().hex()
        data_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(data_hex + get_padding_hex(len(data_hex) // 2)), skey)).decode()
        
        nonce_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(nonce.encode().hex() + "0808080808080808"), skey)).decode()
        
        sha256_raw = calculate_hmac_sha256(data64)
        sha_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sha256_raw.encode().hex() + "10101010101010101010101010101010"), skey)).decode()
        
        sign_content = f"POST\n/api/v1/recovery/erasefrp\nappId=1&data={data64}&sha={sha256_raw}&nonce={nonce}&sid=miui_unlocktool_client"
        sign_hmac = get_hmac_sha1(sign_content)
        sign_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sign_hmac.encode().hex() + "0808080808080808"), skey)).decode()
        
        sig_content = f"POST&/api/v1/recovery/erasefrp&appId={app_id_encrypted}&data={data_encrypted}&nonce={nonce_encrypted}&sha={sha_encrypted}&sid={sid_encrypted}&sign={sign_encrypted}&{ssecurity}"
        signature = base64.b64encode(bytes.fromhex(get_sha1_hash(sig_content))).decode()
        
        response = http.post(f"{MI_HOST}/api/v1/recovery/erasefrp", data={
            'sid': sid_encrypted,
            'data': data_encrypted,
            'appId': app_id_encrypted,
            'nonce': nonce_encrypted,
            'sha': sha_encrypted,
            'sign': sign_encrypted,
            'signature': signature
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'XiaomiPCSuite',
            'Cookie': f"serviceToken={creds['service_token']};userId={user_id};unlockApi_slh=null;unlockApi_ph={creds['unlock_api_ph']}"
        })
        
        encrypted_data = base64.b64decode(response.text.replace('&&&START&&&', ''))
        decrypted = aes_decrypt(encrypted_data, skey)
        json_str = base64.b64decode(decrypted).decode(errors='ignore')
        json_str = json_str.rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
        
        return json.loads(json_str)
    
    except requests.exceptions.RequestException as e:
        print(f"  × 网络连接失败")
        return {"code": -1, "descEN": "网络连接失败"}
    except Exception as e:
        print(f"  × 出错: {e}")
        return {"code": -1, "descEN": str(e)}

def send_mtk_flash(creds, nonce, flash_token):
    """发送 MTK Flash 授权请求"""
    print("\n【步骤 4/4】发送 MTK Flash 授权请求...")
    
    try:
        skey = creds['skey']
        ssecurity = creds['ssecurity']
        user_id = creds['user_id']
        
        request_data = json.dumps({
            "clientId": "mtkFlash",
            "clientVersion": "6.3.706.22",
            "flashToken": flash_token,
            "pcId": generate_random_string(32, False)
        }, separators=(',', ':'))
        
        data64 = base64.b64encode(request_data.encode()).decode()
        
        app_id_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("31" + "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f"), skey)).decode()
        sid_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex("miui_unlocktool_client".encode().hex() + "0a0a0a0a0a0a0a0a0a0a"), skey)).decode()
        
        data_hex = data64.encode().hex()
        data_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(data_hex + get_padding_hex(len(data_hex) // 2)), skey)).decode()
        
        nonce_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(nonce.encode().hex() + "0808080808080808"), skey)).decode()
        
        sha256_raw = calculate_hmac_sha256(data64)
        sha_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sha256_raw.encode().hex() + "10101010101010101010101010101010"), skey)).decode()
        
        sign_content = f"POST\n/api/v1/mtk/flash/ahaFlash\nappId=1&data={data64}&sha={sha256_raw}&nonce={nonce}&sid=miui_unlocktool_client"
        sign_hmac = get_hmac_sha1(sign_content)
        sign_encrypted = base64.b64encode(aes_encrypt_raw(bytes.fromhex(sign_hmac.encode().hex() + "0808080808080808"), skey)).decode()
        
        sig_content = f"POST&/api/v1/mtk/flash/ahaFlash&appId={app_id_encrypted}&data={data_encrypted}&nonce={nonce_encrypted}&sha={sha_encrypted}&sid={sid_encrypted}&sign={sign_encrypted}&{ssecurity}"
        signature = base64.b64encode(bytes.fromhex(get_sha1_hash(sig_content))).decode()
        
        response = http.post(f"{MI_HOST}/api/v1/mtk/flash/ahaFlash", data={
            'sid': sid_encrypted,
            'data': data_encrypted,
            'appId': app_id_encrypted,
            'nonce': nonce_encrypted,
            'sha': sha_encrypted,
            'sign': sign_encrypted,
            'signature': signature
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'XiaomiPCSuite',
            'Cookie': f"serviceToken={creds['service_token']};userId={user_id};unlockApi_slh=null;unlockApi_ph={creds['unlock_api_ph']}"
        })
        
        encrypted_data = base64.b64decode(response.text.replace('&&&START&&&', ''))
        decrypted = aes_decrypt(encrypted_data, skey)
        json_str = base64.b64decode(decrypted).decode(errors='ignore')
        json_str = json_str.rstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
        
        return json.loads(json_str)
    
    except requests.exceptions.RequestException as e:
        print(f"  × 网络连接失败")
        return {"code": -1, "descEN": "网络连接失败"}
    except Exception as e:
        print(f"  × 出错: {e}")
        return {"code": -1, "descEN": str(e)}

def safe_input(prompt):
    """安全输入函数，支持粘贴长文本"""
    print(prompt, end='', flush=True)
    try:
        # 使用 sys.stdin.readline 支持粘贴长文本
        line = sys.stdin.readline()
        if line:
            return line.strip()
        return ""
    except:
        # 备用方案
        return input("").strip()

def show_result(result, success_msg, data_key=None):
    """显示请求结果"""
    print("\n" + "═" * 50)
    if result.get('code') == 0:
        print(f"           ✓ {success_msg}")
        print("═" * 50)
        if data_key and result.get(data_key):
            print(f"\n授权数据 ({data_key}):\n{result.get(data_key)}")
        # 显示其他可能有用的字段
        for key in ['encryptData', 'unlockData', 'flashData', 'data']:
            if key != data_key and result.get(key):
                print(f"\n{key}:\n{result.get(key)}")
    else:
        print(f"           × 请求失败")
        print("═" * 50)
        print(f"\n错误代码: {result.get('code')}")
        print(f"错误信息: {result.get('descEN') or result.get('description') or result.get('desc')}")
        # 显示等待时间信息（解锁时常见）
        if result.get('waitTime'):
            wait_hours = result.get('waitTime', 0) / 3600
            print(f"剩余等待: {wait_hours:.1f} 小时")

def do_auth_request(creds):
    """执行授权请求（选择类型并发送）"""
    print("\n" + "─" * 50)
    print("【选择授权类型】")
    print("  1. FDL 授权 (Fastboot → EDL)")
    print("  2. Bootloader 解锁")
    print("  3. Flash 授权")
    print("  4. 擦除 FRP (Google 锁)")
    print("  5. MTK Flash 授权")
    print("  0. 返回主菜单")
    
    auth_type = input("\n请选择 [0-5]: ").strip()
    
    if auth_type == "0":
        return None
    
    if auth_type not in ["1", "2", "3", "4", "5"]:
        print("\n  × 无效选项")
        return None
    
    print("\n" + "─" * 50)
    print("请输入设备信息：")
    print("  (提示: 可以直接粘贴长文本)")
    
    # 根据授权类型收集参数
    if auth_type in ["1", "2", "4"]:
        # FDL、Bootloader 解锁、擦除 FRP 需要 deviceToken 和 productName
        device_token = safe_input("  设备 Token: ")
        product_name = safe_input("  产品代号 (如 onyx, pine): ")
        
        if not device_token or not product_name:
            print("\n  × 设备信息不完整")
            return None
    
    elif auth_type in ["3", "5"]:
        # Flash 和 MTK Flash 需要 flashToken
        flash_token = safe_input("  Flash Token: ")
        
        if not flash_token:
            print("\n  × Flash Token 不能为空")
            return None
    
    # 获取 Nonce
    nonce = get_nonce(creds)
    if not nonce:
        return None
    
    # 根据类型发送请求
    if auth_type == "1":
        result = send_fdl(creds, nonce, device_token, product_name)
        show_result(result, "FDL 授权成功！", "encryptData")
    
    elif auth_type == "2":
        result = send_unlock(creds, nonce, device_token, product_name)
        show_result(result, "Bootloader 解锁成功！", "encryptData")
    
    elif auth_type == "3":
        result = send_flash(creds, nonce, flash_token)
        show_result(result, "Flash 授权成功！", "flashData")
    
    elif auth_type == "4":
        result = send_erase_frp(creds, nonce, device_token, product_name)
        show_result(result, "擦除 FRP 成功！", "data")
    
    elif auth_type == "5":
        result = send_mtk_flash(creds, nonce, flash_token)
        show_result(result, "MTK Flash 授权成功！", "flashData")
    
    return result

# 兼容旧函数名
def do_fdl_request(creds):
    """兼容旧版本调用"""
    return do_auth_request(creds)

# ==================== 网络设置 ====================

def show_network_settings():
    """显示网络设置菜单"""
    while True:
        print("\n" + "─" * 50)
        print("【网络设置】")
        
        # 显示当前状态
        if http.proxy == "disabled":
            print(f"  当前状态: 已禁用系统代理（直连）")
        elif http.proxy:
            print(f"  当前状态: 使用自定义代理 {http.proxy}")
        else:
            print(f"  当前状态: 使用系统代理")
        
        print("\n请选择：")
        print("  1. 使用系统代理（默认）")
        print("  2. 禁用代理（直连）")
        print("  3. 设置自定义代理")
        print("  4. 返回主菜单")
        
        choice = input("\n请输入选项 [1/2/3/4]: ").strip()
        
        if choice == "1":
            http.enable_system_proxy()
            print("  √ 已切换为系统代理")
        elif choice == "2":
            http.disable_system_proxy()
            print("  √ 已禁用代理，使用直连")
        elif choice == "3":
            proxy = input("  请输入代理地址 (如 http://127.0.0.1:7890): ").strip()
            if proxy:
                http.set_proxy(proxy)
                print(f"  √ 代理已设置为: {proxy}")
            else:
                print("  × 代理地址不能为空")
        elif choice == "4":
            break
        else:
            print("  无效选项")

# ==================== 主程序 ====================

def main():
    print("╔" + "═" * 48 + "╗")
    print("║          小米解锁授权工具                      ║")
    print("║    FDL / Bootloader / Flash / FRP / MTK       ║")
    print("╚" + "═" * 48 + "╝")
    
    # 主循环
    while True:
        # 检查已保存的凭证
        user_id, pass_token = load_token()
        
        if user_id and pass_token:
            print(f"\n当前账号: {user_id}")
            print("\n请选择操作：")
            print("  1. 发送授权请求")
            print("  2. 切换账号（重新扫码登录）")
            print("  3. 网络设置")
            print("  4. 退出程序")
            
            choice = input("\n请输入选项 [1/2/3/4]: ").strip()
            
            if choice == "2":
                clear_token()
                user_id, pass_token = None, None
            elif choice == "3":
                show_network_settings()
                continue
            elif choice == "4":
                print("\n感谢使用，再见！")
                break
            elif choice != "1":
                print("\n无效选项，请重新选择")
                continue
        
        # 如果没有凭证，显示登录菜单
        if not user_id or not pass_token:
            print("\n未检测到已保存的账号")
            print("\n请选择操作：")
            print("  1. 扫码登录")
            print("  2. 网络设置")
            print("  3. 退出程序")
            
            login_choice = input("\n请输入选项 [1/2/3]: ").strip()
            
            if login_choice == "2":
                show_network_settings()
                continue
            elif login_choice == "3":
                print("\n感谢使用，再见！")
                break
            elif login_choice != "1":
                continue
            
            qr = QRLogin()
            result = qr.login()
            
            if not result:
                print("\n登录失败")
                retry = input("是否重试？[Y/n]: ").strip().lower()
                if retry == 'n':
                    break
                continue
            
            user_id = result['userId']
            pass_token = result['passToken']
            
            # 登录成功后询问是否开始请求
            print("\n" + "─" * 50)
            start = input("登录成功！是否立即发送 FDL 请求？[Y/n]: ").strip().lower()
            if start == 'n':
                continue
        
        # 获取凭证
        creds = login_and_get_credentials(user_id, pass_token)
        if not creds:
            print("\n账号凭证已过期，请重新登录")
            clear_token()
            continue
        
        # 执行 FDL 请求
        result = do_fdl_request(creds)
        
        # 请求完成后显示选项
        print("\n" + "─" * 50)
        print("请选择下一步操作：")
        print("  1. 继续请求（换一台设备）")
        print("  2. 切换账号")
        print("  3. 网络设置")
        print("  4. 退出程序")
        
        next_choice = input("\n请输入选项 [1/2/3/4]: ").strip()
        
        if next_choice == "2":
            clear_token()
        elif next_choice == "3":
            show_network_settings()
        elif next_choice == "4":
            print("\n感谢使用，再见！")
            break
        # choice == "1" 或其他情况继续循环

if __name__ == '__main__':
    # 命令行模式
    if len(sys.argv) >= 3:
        if sys.argv[1] == "--clear":
            clear_token()
        else:
            # python fdl_auto.py <deviceToken> <productName>
            user_id, pass_token = load_token()
            if not user_id or not pass_token:
                print("错误：未找到已保存的登录凭证，请先运行交互模式登录")
                sys.exit(1)
            
            creds = login_and_get_credentials(user_id, pass_token)
            if not creds:
                print("错误：凭证已过期，请重新登录")
                sys.exit(1)
            
            nonce = get_nonce(creds)
            if nonce:
                result = send_fdl(creds, nonce, sys.argv[1], sys.argv[2])
                print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        main()
