import os, base64, subprocess
import requests
from PIL import Image, ImageFont

TMP = r"C:\Users\johnf\AppData\Local\Temp\flipper_banner"
OUT_DIR = r"c:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\images"
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

FONT_URLS = {
    "regular": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
    "semibold": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-SemiBold.ttf",
}

def download(url, path):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

regular_path = os.path.join(TMP, "Poppins-Regular.ttf")
semibold_path = os.path.join(TMP, "Poppins-SemiBold.ttf")
if not os.path.exists(regular_path) or os.path.getsize(regular_path) == 0:
    download(FONT_URLS["regular"], regular_path)
if not os.path.exists(semibold_path) or os.path.getsize(semibold_path) == 0:
    download(FONT_URLS["semibold"], semibold_path)

regular_b64 = base64.b64encode(open(regular_path, "rb").read()).decode()
semibold_b64 = base64.b64encode(open(semibold_path, "rb").read()).decode()

BRAND = "Flipper School"
SUB = " - CurAIted Education Videos"
SUBHEAD = "High quality Maths videos for each step from age 5 to 15"

def measure(path, size, text):
    return ImageFont.truetype(path, size).getlength(text)

MAXW = 772  # 820 minus ~48px horizontal padding
best = None
for B in range(56, 22, -1):
    S = round(B * 0.5625)  # matches site's 3.2rem vs 1.8rem ratio
    total = measure(semibold_path, B, BRAND) + measure(semibold_path, S, SUB)
    if total <= MAXW:
        best = (B, S, total)
        break
if best is None:
    best = (22, 12, 0)
B, S, total = best
print("brand size px:", B, "| sub size px:", S, "| headline width px:", round(total, 1))

SUBHEAD_SIZE = 19
print("subheading width px:", round(measure(regular_path, SUBHEAD_SIZE, SUBHEAD), 1))

HEADER_GRADIENT = "linear-gradient(to right, #1e3a5f, #2c5f8d, #4a90c8)"
AI_ACCENT = "#FFD700"

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@font-face {{ font-family:'Poppins'; src:url(data:font/ttf;base64,{regular_b64}) format('truetype'); font-weight:400; font-style:normal; }}
@font-face {{ font-family:'Poppins'; src:url(data:font/ttf;base64,{semibold_b64}) format('truetype'); font-weight:600; font-style:normal; }}
html, body {{ margin:0; padding:0; width:820px; height:360px; overflow:hidden; }}
body {{
  background:
    linear-gradient(135deg, rgba(30,58,95,0.08) 0%, rgba(74,144,200,0.12) 100%),
    linear-gradient(to bottom, #f0f5f9 0%, #e0ecf4 100%);
}}
body::before {{
  content:""; position:fixed; top:0; left:0; right:0; height:4px;
  background: linear-gradient(to right, #1e3a5f, #2c5f8d, #4a90c8); z-index:9999;
}}
.card {{
  position:absolute; top:0; left:0; width:820px; height:360px; box-sizing:border-box;
  background: rgba(255,255,255,0.7);
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:0 24px;
}}
h1 {{
  font-family:'Poppins', sans-serif; font-weight:600; font-size:{B}px;
  margin:0; letter-spacing:-0.5px; line-height:1.1; text-align:center; white-space:nowrap;
}}
.brand {{
  font-size:{B}px; font-weight:600; background:{HEADER_GRADIENT};
  -webkit-background-clip:text; background-clip:text; color:transparent;
  -webkit-text-fill-color:transparent; text-shadow:0 0 0 rgba(30,58,95,0.02);
}}
.sub {{
  font-size:{S}px; font-weight:600; background:{HEADER_GRADIENT};
  -webkit-background-clip:text; background-clip:text; color:transparent;
  -webkit-text-fill-color:transparent; text-shadow:0 0 0 rgba(30,58,95,0.02);
}}
.ai {{ color:{AI_ACCENT}; -webkit-text-fill-color:{AI_ACCENT}; background:none; }}
.subhead {{
  font-family:'Poppins', sans-serif; font-size:{SUBHEAD_SIZE}px; font-weight:400;
  color:#2c5f8d; text-align:center; margin:14px 0 0 0;
}}
</style></head>
<body>
<div class="card">
  <h1>
    <span class="brand">Flipper School</span><span class="sub"> - Cur<span class="ai">AI</span>ted Education Videos</span>
  </h1>
  <p class="subhead">High quality Maths videos for each step from age 5 to 15</p>
</div>
</body></html>
"""

html_path = os.path.join(TMP, "banner.html")
open(html_path, "w", encoding="utf-8").write(html)

png_path = os.path.join(TMP, "banner.png")
chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
url = "file:///" + html_path.replace("\\", "/")
cmd = [chrome, "--headless=new", "--disable-gpu", "--no-first-run",
       "--force-device-scale-factor=1", "--hide-scrollbars",
       "--virtual-time-budget=8000", "--window-size=820,360",
       f"--screenshot={png_path}", url]
subprocess.run(cmd, check=True, timeout=120)

im = Image.open(png_path)
print("screenshot size:", im.size)
if im.size != (820, 360):
    im = im.resize((820, 360), Image.LANCZOS)
im = im.convert("RGB")
out_jpeg = os.path.join(OUT_DIR, "flipper_school_banner_820x360.jpeg")
im.save(out_jpeg, "JPEG", quality=95)
out_html = os.path.join(OUT_DIR, "flipper_school_banner_820x360.html")
open(out_html, "w", encoding="utf-8").write(html)
print("SAVED JPEG:", out_jpeg)
print("SAVED HTML:", out_html)
