<img width="1267" height="704" alt="898c15ba-9f7f-4be9-844f-ff3d75a5f5cf" src="https://github.com/user-attachments/assets/b1d00f1f-c279-43d6-86bf-cd894f8daf85" />
<h1>Usage Tutorial:</h1>

<h2>Supported Platforms: Windows, Linux, MacOS</h2>
<ol>
<li>Install Python and pip (if you don't know how, please search for a tutorial online).</li>
<li>Install pycryptodome:</li>
<pre><code>pip install pycryptodome</code></pre>
<li>Once installed, run the following command:</li>
<pre><code>python xiaomi_auth_fdl_get_sig.py</code></pre>
</ol>

## Notes:

1 - This script requires an official employee ID; it is intended exclusively for use by authorized after-sales service engineers for repair purposes! (Note: Some third-party tools may allow you to input a 'sig' value to trigger EDL mode.)

2 - App for obtaining the login token (provided by RohitVerma882):
[mi_account](https://www.123865.com/s/Q0TTjv-DEE13)

PS: Thanks to 'beichen' for assisting with the reverse engineering of the official after-sales tool. During our analysis of the EDL-triggering mechanism, we discovered an additional HMAC-SHA256 signature verification step; omitting this process results in an "invalid parameter" error (see lines 472–481 for details).
This is the final version—it correctly requests the 'sig'. Please refer to line 432 for instructions on how to replace the 'pcid'.

Warning: If you use this in a public project, you must credit both authors! Warning: If you want to use this public project, you need to credit both authors!!!

## author:
[BEICHEN](https://space.bilibili.com/9784369)

[bgm145632](https://space.bilibili.com/618620472)