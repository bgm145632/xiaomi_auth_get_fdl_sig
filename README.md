<h1>使用教程:</h1>

<h2>支持 Windows, Linux, MacOS :</h2>
<ol>
  <li>安装 Python和pip(不会网络搜索教程)</li>
  <li>安装pycryptodome</li>
  <pre><code>pip install pycryptodome</code></pre>
  <li>完成后输入</li>
  <pre><code>python xiaomi_auth_fdl_get_sig.py</code></pre>
</ol>

## 说明:

1 - 使用此脚本需要工号，仅限官方售后工程师使用/维修！！！(某些第三方工具可以输入sig踢edl)

2 - 获取登录token app(来自RohitVerma882):
[mi_account](https://www.123865.com/s/Q0TTjv-DEE13)

ps:感谢beichen帮我协助逆向官方售后工具，在我们逆向发现踢edl这个工作过程中，发现多了一套HMAC-SHA256额外的签名校验流程，如果没这套流程会提示参数异常（具体看472-481行）

## 作者:
[BEICHEN](https://space.bilibili.com/9784369)

[bgm145632](https://space.bilibili.com/618620472)
