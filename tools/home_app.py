"""Self-contained, offline-safe app metadata and PNG icon for iPhone Home Screen."""
import json
import math
import struct
import zlib

def manifest():
    return json.dumps({
        "name": "ZKTeco Clock Control",
        "short_name": "ZK Clock",
        "description": "Local attendance terminal clock control",
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0c1725",
        "theme_color": "#0c1725",
        "icons": [{"src": "/apple-touch-icon.png",
                   "sizes": "180x180", "type": "image/png", "purpose":"any"}],
    }, ensure_ascii=False).encode("utf-8")

def app_headers(html):
    tags = (
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-title" content="ZK Clock">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
        '<meta name="theme-color" content="#0c1725">'
        '<link rel="manifest" href="/manifest.webmanifest">'
        '<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">'
    )
    if "<head>" in html:
        html = html.replace("<head>", "<head>" + tags, 1)
    return html

def _chunk(name, raw):
    return (struct.pack(">I", len(raw)) + name + raw +
            struct.pack(">I", zlib.crc32(name + raw) & 0xffffffff))

def png_icon(size=180):
    # White hands on a dark blue face. Portable PNG (stdlib, no Pillow).
    rows = []
    cx = cy = size / 2
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            dist = math.hypot(x-cx, y-cy)
            if dist < size*0.37:
                rgb = (35, 118, 207)
                # White clock hands: up and right, from center.
                if ((abs(x-cx) < size*.022 and cy-size*.19 < y < cy+size*.03)
                    or (abs(y-cy)<size*.022 and cx-size*.02 < x < cx+size*.16)
                    or dist < size*.038):
                    rgb = (255,255,255)
            elif dist < size*.41:
                rgb = (141,225,186)
            else:
                rgb = (12,23,37)
            row.extend(rgb)
        rows.append(bytes(row))
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR",header) +
            _chunk(b"IDAT",zlib.compress(b"".join(rows),9)) +
            _chunk(b"IEND",b""))
