# -*- coding: utf-8 -*-
"""识稼日报 · 一键启动

双击桌面图标（启动识稼日报.vbs）后：
  1. 若服务已经在跑 —— 立刻打开浏览器，不开新窗口，也不重复起服务
  2. 若没在跑 —— 后台静默起服务，1.8 秒后自动打开浏览器

命令行直接跑 start.py 会保留控制台输出，便于排查。
"""

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)              # 不切目录，fonts / lib / index.html 会 404

QUIET = "--quiet" in sys.argv
PORTS = (80, 8000, 8080, 5000)
MARK = "识稼日报"

# 无窗口模式（pythonw）下 stdout 是 None，所有输出改写到日志，避免 print 崩溃
if QUIET:
    try:
        _log = open(os.path.join(HERE, "运行日志.txt"), "a", encoding="utf-8")
        _log.write("\n--- %s ---\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        sys.stdout = _log
        sys.stderr = _log
    except Exception:
        try:
            sys.stdout = open(os.devnull, "w")
            sys.stderr = sys.stdout
        except Exception:
            pass
elif sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk", errors="replace")
    except Exception:
        pass


def url_for(host, port):
    return "http://%s" % host if port == 80 else "http://%s:%d" % (host, port)


def is_running(port):
    """这个端口上跑的是不是本服务 —— 认页面里有没有「识稼日报」。"""
    try:
        with urllib.request.urlopen(url_for("127.0.0.1", port) + "/", timeout=2) as r:
            return MARK in r.read(3000).decode("utf-8", "ignore")
    except Exception:
        return False


def port_free(p):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", p))
        return True
    except OSError:
        return False
    finally:
        s.close()


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("223.5.5.5", 80))     # 只为让系统选出口网卡，不发包
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip.startswith(("10.", "192.168.", "172.")):
                return ip
    except Exception:
        pass
    return "127.0.0.1"


def write_addr_file(port):
    """手机地址落成文件，随时可查；每次启动都刷新。"""
    try:
        with open(os.path.join(HERE, "手机访问地址.txt"), "w", encoding="utf-8") as f:
            f.write("手机打开这个地址：\n\n    %s\n\n电脑：%s\n\n"
                    "（手机要和电脑连同一个 WiFi；换网后地址会变，重新双击图标即自动更新本文件）\n"
                    % (url_for(lan_ip(), port), url_for("127.0.0.1", port)))
    except Exception:
        pass


# ---------- 1. 已经在跑：秒开，不重复起服务 ----------
for p in PORTS:
    if is_running(p):
        write_addr_file(p)
        webbrowser.open(url_for("127.0.0.1", p))
        sys.exit(0)

# ---------- 2. 挑一个空闲端口 ----------
port = next((p for p in PORTS if port_free(p)), None)
if port is None:
    print("80 / 8000 / 8080 / 5000 都被占用了，先关掉占用它们的程序。")
    sys.exit(1)

ip = lan_ip()

write_addr_file(port)

if not QUIET:
    print()
    print("=" * 48)
    print("        识稼日报 · 作物病害智能识别")
    print("=" * 48)
    print()
    print("    电脑打开：", url_for("127.0.0.1", port))
    print("    手机打开：", url_for(ip, port))
    print()
    print("    关掉这个窗口服务就停了；想无窗口运行请双击桌面图标。")
    print("=" * 48)
    print()


def open_browser_later():
    time.sleep(1.8)          # 等服务真起来，免得浏览器打开是「拒绝连接」
    try:
        webbrowser.open(url_for("127.0.0.1", port))
    except Exception:
        pass


threading.Thread(target=open_browser_later, daemon=True).start()

import uvicorn

try:
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="warning")
except KeyboardInterrupt:
    pass
