# -*- coding: utf-8 -*-
"""本机二维码：给启动器用，纯标准库 + qrcode（不含 Pillow）

生成两个文件，都放在程序目录：
    手机扫码.png   —— 二维码图片，可直接打印/发微信
    手机扫码.html  —— 带二维码和地址的一张“告示”，双击就能全屏看

只依赖 qrcode 的矩阵，PNG 由本文件自己按 1 位灰度格式写出来，
所以不需要 Pillow，塞进绿色 Python 也不会多出几十 MB。
"""

import base64
import html
import os
import struct
import zlib


# ---------- 1. 二维码矩阵 ----------
def matrix_of(text, border=4):
    import qrcode
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)
    return qr.get_matrix()


# ---------- 2. 自己写一张 1 位灰度 PNG（不依赖 Pillow）----------
def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path, matrix, scale=9):
    """matrix 是 qrcode 的 get_matrix()：True=黑格，已含白边。"""
    n = len(matrix)
    side = n * scale
    rowbytes = (side + 7) // 8

    raw = bytearray()
    for y in range(side):
        raw.append(0)                     # 每行的 filter type：0 = None
        mrow = matrix[y // scale]
        row = bytearray(rowbytes)
        for x in range(side):
            # 1 位灰度里 0=黑、1=白，所以白格才置位
            if not mrow[x // scale]:
                row[x >> 3] |= 0x80 >> (x & 7)
        raw.extend(row)

    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 1, 0, 0, 0, 0))
           + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + _chunk(b"IEND", b""))

    with open(path, "wb") as f:
        f.write(png)
    return side


# ---------- 3. 一张纸质的“扫码告示” ----------
_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>识稼日报 · 手机扫码</title>
<style>
  html, body {{ height: 100%; }}
  body {{
    margin: 0; background: #e9dcbc; color: #1a140d;
    font-family: "Songti SC", "SimSun", "STSong", serif;
    display: flex; align-items: center; justify-content: center;
    -webkit-text-stroke: 0.28px currentColor;
  }}
  .card {{
    background: #f7f0dd; padding: 34px 46px 30px; text-align: center;
    border: 1px solid #241f18; outline: 1px solid rgba(36,31,24,.18); outline-offset: 5px;
    box-shadow: 0 10px 34px rgba(60,45,25,.14);
  }}
  h1 {{ font-size: 26px; letter-spacing: 6px; margin: 0 0 4px; }}
  .sub {{ font-size: 12px; letter-spacing: 3px; color: #4a4134; }}
  img {{ display: block; width: 264px; height: 264px; margin: 18px auto 14px; image-rendering: pixelated; }}
  .url {{ font-size: 24px; color: #8B0000; font-weight: 700; letter-spacing: 1px; }}
  .tip {{ font-size: 13px; line-height: 2; color: #4a4134; margin: 14px 0 0; }}
  .tip b {{ color: #8B0000; }}
</style>
</head>
<body>
  <div class="card">
    <h1>识稼日报</h1>
    <div class="sub">手机扫码 · 打开本报</div>
    <img src="{img}" alt="二维码">
    <div class="url">{url}</div>
    <p class="tip">
      手机要先连上<b>同一个 WiFi</b>（这台电脑现在连的是 {ssid}）<br>
      扫不开就把上面的地址手动输一遍；页面加载 3D 模型要等几秒
    </p>
  </div>
</body>
</html>
"""


def _ssid():
    """读当前 WiFi 名字；读不到就留空，不影响使用。"""
    try:
        import subprocess
        out = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, timeout=5,
            creationflags=0x08000000,      # CREATE_NO_WINDOW：pythonw 下不闪黑框
        ).stdout
        for enc in ("utf-8", "gbk", "mbcs"):
            try:
                text = out.decode(enc)
            except Exception:
                continue
            for line in text.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "当前网络"


def generate(url, out_dir, name="手机扫码"):
    """写出 手机扫码.png / 手机扫码.html，返回 html 的绝对路径。"""
    matrix = matrix_of(url)
    png_path = os.path.join(out_dir, name + ".png")
    write_png(png_path, matrix, scale=9)

    with open(png_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("ascii")

    page_path = os.path.join(out_dir, name + ".html")
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(_PAGE.format(
            img="data:image/png;base64," + img_b64,
            url=html.escape(url),
            ssid=html.escape(_ssid()),
        ))
    return page_path
