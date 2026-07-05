#!/usr/bin/env python3
"""claude.ai 아티팩트용 단일 파일 빌드.

사용법 (repo 루트에서):
  1) python3 tools/build_artifact.py            # dist/playbook_artifact.html 생성
  2) Claude에게 "아티팩트 갱신해줘" → Artifact 도구로 재발행 (URL 유지)

파이프라인: index.html에서 JSX 추출 → esbuild 컴파일(npx 필요) →
React 18 prod UMD + tools/artifact_tailwind.css + 인라인 썸네일(data URI) 조립.
주의: artifact_tailwind.css는 수동 생성 유틸리티 CSS — 덮어쓰지 말 것.
새 tailwind 클래스를 쓰면 이 파일에 규칙 추가 필요.
"""
import base64, glob, json, os, re, subprocess, sys, tempfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)

src = open(os.path.join(ROOT, "index.html")).read()
jsx = re.search(r'<script type="text/babel"[^>]*>(.*?)</script>\s*</body>', src, re.S).group(1)
styles = re.search(r'<style>(.*?)</style>', src, re.S).group(1)

with tempfile.NamedTemporaryFile("w", suffix=".jsx", delete=False) as f:
    f.write(jsx); jsx_path = f.name
out_js = jsx_path.replace(".jsx", ".js")
subprocess.run(["npx", "--yes", "esbuild", jsx_path, "--loader:.jsx=jsx",
                "--minify-whitespace", f"--outfile={out_js}"], check=True)
js = open(out_js).read()

def fetch(url, cache):
    p = os.path.join(ROOT, "tools", cache)
    if not os.path.exists(p):
        urllib.request.urlretrieve(url, p)
    return open(p).read()
react = fetch("https://unpkg.com/react@18.3.1/umd/react.production.min.js", "react.min.js")
reactdom = fetch("https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js", "react-dom.min.js")

thumbs = {}
for f in sorted(glob.glob(os.path.join(ROOT, "thumbs", "*.jpg"))):
    cid = os.path.basename(f)[:-4]
    # 원본이 크면 240px 축소본 권장 (ffmpeg -vf scale=240:-2 -q:v 6)
    thumbs[cid] = "data:image/jpeg;base64," + base64.b64encode(open(f, "rb").read()).decode()

js = re.sub(r'thumbnail_url:\s*"thumbs/(C\d+)\.jpg"', r'thumbnail_url:THUMBS["\1"]||null', js)
js = re.sub(r'"thumbs/"\s*\+\s*([A-Za-z_.$]+(?:\.[A-Za-z_$]+)?)\s*\+\s*"\.jpg"', r'(THUMBS[\1]||"")', js)

html = f"""<title>색동서울 콘텐츠 플레이북</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<script>
(function() {{
  var m = document.querySelector('meta[name=viewport]');
  if (!m) {{ m = document.createElement('meta'); m.name = 'viewport'; m.content = 'width=device-width, initial-scale=1, viewport-fit=cover'; }}
  document.head.appendChild(m);
}})();
</script>
<style>
{open(os.path.join(ROOT, "tools", "artifact_tailwind.css")).read()}
</style>
<style>
{styles}
</style>
<div id="root"></div>
<script>{react}</script>
<script>{reactdom}</script>
<script>
const THUMBS = {json.dumps(thumbs)};
{js}
</script>
"""
out = os.path.join(ROOT, "dist", "playbook_artifact.html")
open(out, "w").write(html)
print(f"built {out} ({len(html)//1024} KB)")
