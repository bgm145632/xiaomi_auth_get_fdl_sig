#!/usr/bin/env python3
import os
import shutil

def get_pip_command():
    if shutil.which("pip3"):
        return "pip3"
    elif shutil.which("pip"):
        return "pip"
    else:
        raise EnvironmentError("NO,PIP")

for lib in ['Cryptodome', 'urllib3', 'requests', 'colorama']:
    try:
        __import__(lib)
    except ImportError:
        prefix = os.getenv("PREFIX", "")
        pip_cmd = get_pip_command()
        if lib == 'Cryptodome':
            if "com.termux" in prefix:
                cmd = 'pkg install python-pycryptodomex'
            else:
                cmd = f'{pip_cmd} install pycryptodomex'
        else:
            cmd = f'{pip_cmd} install {lib}'
        os.system(cmd)

import requests, json, hmac, random, binascii, urllib, hashlib, urllib.parse, shutil
from base64 import b64encode, b64decode
from Cryptodome.Cipher import AES
from urllib.parse import urlparse, parse_qs
from colorama import init, Fore, Style
init(autoreset=True)

cg = Style.BRIGHT + Fore.GREEN
cr = Fore.RED
cy = Style.BRIGHT + Fore.YELLOW
cb = Style.BRIGHT + Fore.BLUE
cres = Style.RESET_ALL

class XiaomiUnlockTool:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {"User-Agent": "XiaomiPCSuite"}
        
        self.config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
        self.data_dir = os.path.join(self.config_dir, "xiaomi_gettoken")
        os.makedirs(self.data_dir, exist_ok=True)
        self.datafile = os.path.join(self.data_dir, "xiaomi_token.json")
        
        self.auth_info = {}
        self.ssecurity = None
        self.nonce = None
        self.cookies = {}
        
        self.current_host = "unlock.update.miui.com"
    
    def check_existing_login(self):
        if not os.path.isfile(self.datafile):
            return False
        
        try:
            with open(self.datafile, "r") as file:
                data = json.load(file)
            
            if data and data.get("login") == "ok":
                print(f"\n{cy}检测到已保存的账户: {data.get('userid', 'Unknown')}{cres}")
                choice = input(f"{cg}是否使用此账户? (y/N): {cres}").strip().lower()
                
                if choice == 'y':
                    if data.get("full_token"):
                        return self.login_with_full_token(data["full_token"])
                    elif data.get("passtoken") and data.get("userid"):
                        return self.login_with_saved_passtoken(data)
                    else:
                        print(f"{cr}保存的登录信息不完整{cres}")
                        os.remove(self.datafile)
                        return False
                elif choice == '删除':
                    print(f"{cy}删除保存的登录信息...{cres}")
                    os.remove(self.datafile)
                    return False
                else:
                    return False
            else:
                os.remove(self.datafile)
                return False
                
        except (PermissionError, json.JSONDecodeError):
            if os.path.exists(self.datafile):
                os.remove(self.datafile)
            return False
    
    def decode_full_token(self, token_b64):
        try:
            token_json = b64decode(token_b64).decode('utf-8')
            token_data = json.loads(token_json)
            return token_data
        except Exception as e:
            print(f"{cr}解码token失败: {e}{cres}")
            return None
    
    def login_with_full_token(self, token_b64):
        token_data = self.decode_full_token(token_b64)
        if not token_data:
            return False
        
        passToken = token_data.get("passToken")
        userId = token_data.get("userId")
        deviceId = token_data.get("deviceId")
        
        if not passToken or not userId:
            print(f"{cr}token中缺少必要的参数{cres}")
            return False
        
        print(f"{cg}Token解码成功{cres}")
        return self.request_unlock_service(passToken, userId, deviceId)
    
    def login_with_saved_passtoken(self, data):
        passToken = data.get("passtoken")
        userId = data.get("userid")
        
        if not passToken or not userId:
            print(f"{cr}保存的登录信息不完整{cres}")
            os.remove(self.datafile)
            return False
        
        deviceId = ''.join(random.choices('0123456789abcdef', k=16))
        return self.request_unlock_service(passToken, userId, deviceId)
    
    def request_unlock_service(self, passToken, userId, deviceId):
        print(f"{cy}请求登录信息...{cres}")
        
        unlock_response = self.session.get(
            "https://account.xiaomi.com/pass/serviceLogin?sid=unlockApi&_json=true&passive=true&hidden=true",
            headers=self.headers,
            cookies={
                'passToken': passToken,
                'userId': userId,
                'deviceId': deviceId
            }
        )
        
        try:
            unlock_data = json.loads(unlock_response.text.replace("&&&START&&&", ""))
        except:
            print(f"{cr}解析解锁服务响应失败{cres}")
            return False
        
        print(f"{cy}解锁服务响应: {cb}{json.dumps(unlock_data, indent=2, ensure_ascii=False)}{cres}")
        if unlock_data.get("code") != 0:
            error_msg = unlock_data.get("desc", "未知错误")
            print(f"{cr}解锁服务返回错误: {error_msg}{cres}")
            return False
        
        if "ssecurity" not in unlock_data:
            print(f"{cr}无法获取ssecurity参数!{cres}")
            return False
        
        if "location" not in unlock_data:
            print(f"{cr}无法获取location参数!{cres}")
            return False
        
        location_url = unlock_data["location"]
        parsed_url = urlparse(location_url)
        query_params = parse_qs(parsed_url.query)
        
        nonce = query_params.get('nonce', [None])[0]
        if not nonce:
            print(f"{cr}无法从location中获取nonce参数!{cres}")
            return False
        
        self.ssecurity = unlock_data["ssecurity"]
        self.nonce = nonce
        
        print(f"{cy}获取到的认证参数:{cres}")
        print(f"  ssecurity: {self.ssecurity[:20]}...")
        print(f"  nonce: {self.nonce}")
        print(f"  location: {location_url[:50]}...")
        
        return self.complete_authentication(location_url, userId, passToken)
    
    def complete_authentication(self, location_url, userId, passToken):
        print(f"{cy}完成认证流程...{cres}")
        
        client_sign = urllib.parse.quote_plus(
            b64encode(
                hashlib.sha1(f"nonce={self.nonce}".encode("utf-8") + b"&" + self.ssecurity.encode("utf-8")).digest()
            )
        )
        
        response = self.session.get(
            location_url + "&clientSign=" + client_sign,
            headers=self.headers
        )
        
        self.cookies = {cookie.name: cookie.value for cookie in response.cookies}
        
        if 'serviceToken' not in self.cookies:
            print(f"{cr}获取serviceToken失败！请使用验证码登录一次！.{cres}")
            return False
        
        self.auth_info = {
            "login": "ok",
            "userid": userId,
            "passtoken": passToken,
            "ssecurity": self.ssecurity,
            "nonce": self.nonce,
            "passtoken_used": True
        }
        self.save_data(self.auth_info)
        
        print(f"\n{cg}DONE！登录成功!{cres}")
        print(f"{cg}账户信息:{cres}\nID: {userId}")
        return True
    
    def hex_to_base64(self, hex_string):
        try:
            hex_string = hex_string.strip()
            bytes_data = bytes.fromhex(hex_string)
            base64_data = b64encode(bytes_data).decode('utf-8')
            return base64_data
        except Exception as e:
            print(f"{cr}十六进制转换失败: {e}{cres}")
            return None
    
    def save_token_bin(self, encrypt_data):
        try:
            hex_string = encrypt_data.strip()
            binary_data = bytes.fromhex(hex_string)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            token_file = os.path.join(script_dir, "fdl_token.bin")  # 改名以区分
            with open(token_file, 'wb') as f:
                f.write(binary_data)
            print(f"{cg}FDL数据已保存为: {token_file}{cres}")
            return True
        except Exception as e:
            print(f"{cr}保存文件失败: {e}{cres}")
            return False
    
    def authenticate_with_full_token(self):
        print(f"\n{cy}使用完整token登录{cres}")
        print(f"{cb}请输入完整的token字符串:{cres}")
        print(f"{cy}格式: base64编码的JSON或十六进制字符串{cres}")
        
        token_input = input(f"\n{cy}请输入token: {cres}").strip()
        if not token_input:
            print(f"{cr}token不能为空{cres}")
            return False
        
        token_b64 = None
        try:
            if all(c in '0123456789abcdefABCDEF' for c in token_input):
                print(f"{cy}检测到十六进制token，正在转换...{cres}")
                token_b64 = self.hex_to_base64(token_input)
                if not token_b64:
                    return False
            else:
                token_b64 = token_input
        except:
            token_b64 = token_input
        
        token_data = self.decode_full_token(token_b64)
        if not token_data:
            return False
        
        passToken = token_data.get("passToken")
        userId = token_data.get("userId")
        deviceId = token_data.get("deviceId")
        
        if not passToken or not userId:
            print(f"{cr}token中缺少passToken或userId{cres}")
            return False
        
        if not deviceId:
            deviceId = ''.join(random.choices('0123456789abcdef', k=16))
        
        self.auth_info = {
            "login": "ok",
            "userid": userId,
            "full_token": token_b64,
            "passtoken_used": True
        }
        
        return self.request_unlock_service(passToken, userId, deviceId)
    
    def authenticate_with_passtoken(self):
        print(f"\n{cy}使用passtoken登录{cres}")
        print(f"{cb}步骤1: 获取passtoken{cres}")
        print(f"{cy}请按以下步骤操作:{cres}")
        print(f"1. 打开浏览器访问: {cb}https://account.xiaomi.com{cres}")
        print(f"2. 登录您的小米账户")
        print(f"3. 按F12打开开发者工具")
        print(f"4. 进入Application/Storage标签页")
        print(f"5. 在Cookies中找到 {cb}passToken{cres} 的值")
        print(f"6. 同时找到 {cb}userId{cres} 的值")
        
        passToken = input(f"\n{cy}请输入passToken: {cres}").strip()
        userId = input(f"{cy}请输入userId: {cres}").strip()
        
        if not passToken or not userId:
            print(f"{cr}passToken和userId不能为空{cres}")
            return False
        
        deviceId = ''.join(random.choices('0123456789abcdef', k=16))
        return self.request_unlock_service(passToken, userId, deviceId)
    
    def save_data(self, data):
        with open(self.datafile, "w") as file:
            json.dump(data, file, indent=2)
    
    def get_device_info(self):
        print(f"\n{cy}获取设备信息{cres}")
        
        product = input(f"{cy}请输入设备型号 (product): {cres}").strip()
        if not product:
            print(f"{cr}设备型号不能为空{cres}")
            exit(1)
        
        token = input(f"{cy}请输入设备Token: {cres}").strip()
        if not token:
            print(f"{cr}设备Token不能为空{cres}")
            exit(1)
        
        print(f"{cg}设备型号: {product}{cres}")
        print(f"{cg}设备Token: {token}{cres}")
        return product, token

    class RetrieveEncryptData:
        def __init__(self, unlock_api, path, params):
            self.unlock_api = unlock_api
            self.path = path
            self.params = {k.encode("utf-8"): 
                (v.encode("utf-8") if isinstance(v, str) 
                 else b64encode(json.dumps(v).encode("utf-8")) if not isinstance(v, bytes) 
                 else v) 
                for k, v in params.items()}
        
        def add_nonce(self):
            print(f"{cy}获取nonce...{cres}")
            r = XiaomiUnlockTool.RetrieveEncryptData(
                self.unlock_api,
                "/api/v2/nonce", 
                {
                    "r": ''.join(random.choices(list("abcdefghijklmnopqrstuvwxyz"), k=16)), 
                    "sid": "miui_unlocktool_client"
                }
            ).run()
            
            if r and "nonce" in r:
                self.params[b"nonce"] = r["nonce"].encode("utf-8")
                self.params[b"sid"] = b"miui_unlocktool_client"
                print(f"{cg}获取nonce成功{cres}")
            else:
                print(f"{cr}获取nonce失败: {r}{cres}")
                if hasattr(self.unlock_api, 'nonce') and self.unlock_api.nonce:
                    self.params[b"nonce"] = self.unlock_api.nonce.encode("utf-8")
                    self.params[b"sid"] = b"miui_unlocktool_client"
                    print(f"{cy}使用当前nonce继续{cres}")
                else:
                    raise Exception("无法获取nonce")
            return self
        
        def getp(self, sep):
            return b'POST' + sep + self.path.encode("utf-8") + sep + b"&".join([
                k + b"=" + v for k, v in self.params.items()
            ])
        
        def run(self):
            try:
                if not self.unlock_api.ssecurity:
                    return {"error": "ssecurity为空，请重新登录"}
                
                self.params[b"sign"] = binascii.hexlify(
                    hmac.digest(
                        b'2tBeoEyJTunmWUGq7bQH2Abn0k2NhhurOaqBfyxCuLVgn4AVj7swcawe53uDUno', 
                        self.getp(b"\n"), 
                        "sha1"
                    )
                )
                
                ssecurity_bytes = b64decode(self.unlock_api.ssecurity)
                
                for k, v in self.params.items():
                    padded_data = v + (16 - len(v) % 16) * bytes([16 - len(v) % 16])
                    encrypted = AES.new(ssecurity_bytes, AES.MODE_CBC, b"0102030405060708").encrypt(padded_data)
                    self.params[k] = b64encode(encrypted)
                
                self.params[b"signature"] = b64encode(
                    hashlib.sha1(
                        self.getp(b"&") + b"&" + self.unlock_api.ssecurity.encode("utf-8")
                    ).digest()
                )
                
                post_data = {}
                for k, v in self.params.items():
                    post_data[k.decode('utf-8')] = v.decode('utf-8')
                
                url = f"https://{self.unlock_api.current_host}{self.path}"
                print(f"{cy}发送请求到: {url}{cres}")
                
                response = self.unlock_api.session.post(
                    url, 
                    data=post_data,
                    headers=self.unlock_api.headers, 
                    cookies=self.unlock_api.cookies,
                    timeout=30
                )
                
                print(f"{cy}收到响应，状态码: {response.status_code}{cres}")
                
                if not response.text.strip():
                    return {"error": "服务器返回空响应"}
                
                try:
                    decrypt_cipher = AES.new(ssecurity_bytes, AES.MODE_CBC, b"0102030405060708")
                    encrypted_response = b64decode(response.text)
                    decrypted = decrypt_cipher.decrypt(encrypted_response)
                    decrypted = decrypted[:-decrypted[-1]]
                    result = json.loads(b64decode(decrypted))
                    return result
                except Exception as e:
                    print(f"{cr}解密响应失败: {e}{cres}")
                    try:
                        return json.loads(response.text)
                    except:
                        return {"error": f"解密失败: {e}", "raw_response": response.text}
                    
            except Exception as e:
                print(f"{cr}请求执行失败: {e}{cres}")
                return {"error": str(e)}
    
    def request_fdl(self, product, token):
        """请求FDL授权（Fastboot to EDL）"""
        print(f"\n{cy}请求FDL授权...{cres}")
        
        userId = self.auth_info.get("userid")
        pc_id = ''.join(random.choices('0123456789abcdef', k=32))
        
        request_data = {
            "clientId": "2",
            "clientVersion": "6.6.816.30",
            "deviceInfo": {
                "boardVersion": "",
                "deviceName": "",
                "product": product,
                "socId": "",
            },
            "deviceToken": token,
            "language": "en",
            "operate": "unlock",
            "pcId": pc_id,
            "region": "",
            "uid": userId,
        }
        
        req = self.RetrieveEncryptData(
            self,
            "/api/v2/fastboot2edl",
            {
                "appId": "1",
                "data": request_data,
            }
        )
        
        data_bytes = req.params.get(b"data")
        if not data_bytes:
            print(f"{cr}无法获取data参数{cres}")
            return None
        data64 = data_bytes.decode('utf-8')
        
        HMAC_SHA256_KEY = "B288B376D22C73E6BE8EA5AF36E5275E6FA67EDADF8B18F2E5D88ACA9A92E4A1"
        sha_raw = hmac.new(HMAC_SHA256_KEY.encode(), data64.encode(), hashlib.sha256).hexdigest()
        req.params[b"sha"] = sha_raw.encode('utf-8')
        req.add_nonce()
        nonce_val = req.params.pop(b"nonce")
        sid_val = req.params.pop(b"sid")
        sha_val = req.params.pop(b"sha") 
        req.params[b"nonce"] = nonce_val
        req.params[b"sha"] = sha_val
        req.params[b"sid"] = sid_val
        
        result = req.run()
        return result
    
    def run(self):
        print(f"{cg}{'='*70}{cres}")
        print(f"{cb}                小米FDL算命工具 (Fastboot→EDL) {cres}")
        print(f"{cb}项目                https://github.com/bgm145632/xiaomi_get_unlock-code{cres}")
        print(f"                                         {cres}")
        print(f"{cb}作者                          BEICHEN，bgm145632{cres}")
        print(f"{cb}参考项目                       termux-miunlock{cres}")
        print(f"                                         {cres}")
        print(f"{cb}风破浪会有时 直挂云帆济沧海{cres}")
        print(f"{cg}{'='*70}{cres}")
        
        try:
            if not self.check_existing_login():
                print(f"\n{cy}需要登录小米账户{cres}")
                print(f"{cy}请选择登录方式:{cres}")
                print(f"1. 使用完整token (推荐)")
                print(f"2. 使用passtoken和userid (需要保持浏览器账户没退出)")
                
                choice = input(f"\n{cy}请选择 (默认1): {cres}").strip() or "1"
                
                if choice == "1":
                    if not self.authenticate_with_full_token():
                        return
                else:
                    if not self.authenticate_with_passtoken():
                        return
            
            product, device_token = self.get_device_info()
            if not product or not device_token:
                print(f"{cr}设备信息不完整{cres}")
                return
            
            input(f"\n{cy}按 Enter 请求FDL授权...{cres}")
            result = self.request_fdl(product, device_token)
            
            if not result:
                print(f"{cr}FDL请求失败 - 无响应{cres}")
                return
                
            print(f"\n{cy}服务器响应:{cres}")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if "code" in result and result["code"] == 0:
                encrypt_data = result.get("encryptData")
                if encrypt_data and isinstance(encrypt_data, str) and len(encrypt_data) > 10:
                    print(f"\n{cg}FDL授权成功!{cres}")
                    print(f"{cb}{'='*50}{cres}")
                    print(f"{cg}encryptData:{cres}")
                    print(f"{cy}{encrypt_data}{cres}")
                    print(f"{cb}{'='*50}{cres}")
                    
                    print(f"{cy}正在生成fdl_token.bin文件...{cres}")
                    if self.save_token_bin(encrypt_data):
                        print(f"{cg}文件生成成功!{cres}")
                    else:
                        print(f"{cr}文件生成失败{cres}")                            
                else:
                    print(f"{cr}响应中缺少有效的encryptData{cres}")
            elif "descCN" in result:
                print(f"\n{cr}授权失败: {result['descCN']}{cres}")        
            else:
                print(f"\n{cr}未知的响应格式{cres}")
            
            print(f"\n{cg}{'='*70}{cres}")
            print(f"{cg}                    流程完成!{cres}")
            print(f"{cg}{'='*70}{cres}")
            
        except KeyboardInterrupt:
            print(f"\n{cy}用户取消操作{cres}")
        except Exception as e:
            print(f"\n{cr}发生错误: {e}{cres}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    tool = XiaomiUnlockTool()
    tool.run()