from pathlib import Path
p=Path(__file__).resolve().parent / "index.html"
s=p.read_text()
if '<script src="factory.js"></script>' not in s:
    s=s.replace('</head>', '<link rel="stylesheet" href="factory.css">\n</head>', 1)
    s=s.replace('内容工厂 · 成稿线', '内容工厂 · 视频生产线', 1)
    pos=s.rfind('</body>')
    if pos < 0: raise SystemExit('index.html 格式不符')
    s=s[:pos]+'<script src="factory.js"></script>\n'+s[pos:]
    p.write_text(s)
print('内容工厂页面已接入。运行 python3 server.py 后打开 http://127.0.0.1:8765')
