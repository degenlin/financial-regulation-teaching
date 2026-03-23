
"""
直接双击此文件即可启动金融监管教学实验系统
"""
import os, sys, subprocess, webbrowser, time

BASE = os.path.dirname(os.path.abspath(__file__))
SYS_DIR = os.path.join(BASE, "教学系统")

print("=" * 50)
print("  金融监管教学实验系统  启动中...")
print("=" * 50)
print()
print("  教师账号: teacher / teacher123")
print("  访问地址: http://127.0.0.1:5000")
print()

# 检查并安装 Flask
try:
    import flask
except ImportError:
    print("  正在安装 Flask...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "-q"])
    print("  Flask 安装完成")

# 延迟打开浏览器
def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")

import threading
t = threading.Thread(target=open_browser, daemon=True)
t.start()

# 启动 Flask
os.chdir(SYS_DIR)
sys.path.insert(0, SYS_DIR)
import app as fsapp
fsapp.init_db()
fsapp.app.run(host="0.0.0.0", port=5000, debug=False)
