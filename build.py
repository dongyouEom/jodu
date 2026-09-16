#!/usr/bin/env python3
"""regions.json + template*.html -> dist/  (python3 build.py)

dist/index.html          루트(허브): 브랜드 소개 + 전체 지역 목록
dist/<slug>/index.html   지역별 페이지 (검색엔진이 지역마다 별도 URL로 색인)
dist/style.css, assets/, sitemap.xml, robots.txt, (커스텀 도메인이면) CNAME
"""
import json, pathlib, re, shutil
from urllib.parse import urlparse

root = pathlib.Path(__file__).parent
cfg = json.loads((root / "regions.json").read_text(encoding="utf-8"))
tpl_region = (root / "template.html").read_text(encoding="utf-8")
tpl_index = (root / "template-index.html").read_text(encoding="utf-8")
dist = root / "dist"

# ---- regions.json 검증: 비개발자 편집 실수를 빌드 단계에서 잡는다 -------------------------
def die(msg):
    raise SystemExit(f"\n[regions.json 오류] {msg}\n")

for k in ("brand", "phone", "telegram", "domain", "hours", "regions"):
    if k not in cfg: die(f'"{k}" 항목이 없습니다.')
if not cfg["regions"]: die('"regions"가 비어 있습니다. 지역을 1개 이상 넣어주세요.')
seen = set()
for i, r in enumerate(cfg["regions"], 1):
    for k in ("slug", "name", "areas", "city"):
        if k not in r: die(f'{i}번째 지역에 "{k}"가 없습니다: {r}')
    if not re.fullmatch(r"[a-z0-9-]+", r["slug"]):
        die(f'slug "{r["slug"]}"는 영문 소문자·숫자·하이픈만 가능합니다 (URL 경로로 쓰임).')
    if r["slug"] in seen: die(f'slug "{r["slug"]}"가 중복됩니다.')
    seen.add(r["slug"])
    if not isinstance(r["areas"], list) or not r["areas"]:
        die(f'{r["name"]}의 "areas"는 1개 이상의 목록이어야 합니다.')

# ---- dist/assets/ 에 직접 넣은 파일 복구 (빌드 때 dist가 지워지므로 원본 assets/ 로 옮긴다) ----
_src, _out, _man = root / "assets", dist / "assets", dist / ".assets-manifest"
if _out.is_dir():
    built = set(_man.read_text().split()) if _man.exists() else set()
    _src.mkdir(exist_ok=True)
    for f in _out.iterdir():
        if f.is_file() and f.name not in built and not (_src / f.name).exists():
            shutil.copy2(f, _src / f.name)
            print(f"복구: dist/assets/{f.name} -> assets/{f.name}  (파일은 assets/ 에 넣어주세요)")

shutil.rmtree(dist, ignore_errors=True)
dist.mkdir()

domain = cfg["domain"].rstrip("/")
regions = cfg["regions"]
assets = root / "assets"
IMG = {".gif", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg"}
VID = {".mp4", ".webm"}
j = lambda x: json.dumps(x, ensure_ascii=False)
esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")

# ---- 갤러리 ---------------------------------------------------------------------------
def media_items():
    if not assets.is_dir():
        return []
    items = cfg.get("media")
    if items is None:  # media 항목이 없으면 assets/ 전체를 파일명 순으로
        items = [{"file": f.name} for f in sorted(assets.iterdir()) if f.suffix.lower() in IMG | VID]
    out = []
    for it in items:
        f = assets / it["file"]
        if not f.is_file():
            print(f"skip (없음): assets/{it['file']}"); continue
        out.append((f, it.get("caption", "")))
    return out

MEDIA = media_items()

def media_html(prefix):
    figs = []
    for f, cap in MEDIA:
        src = f"{prefix}assets/{f.name}"
        if f.suffix.lower() in VID:
            tag = f'<video src="{src}" autoplay muted loop playsinline></video>'
        else:
            tag = f'<img src="{src}" alt="{esc(cap)}" loading="lazy">'
        figs.append(f"<figure>{tag}{f'<figcaption>{esc(cap)}</figcaption>' if cap else ''}</figure>")
    if not figs:
        return ""
    return '  <section>\n    <div class="gallery">' + "".join(figs) + "</div>\n  </section>"

if MEDIA:
    shutil.copytree(assets, dist / "assets", ignore=lambda d, names: [n for n in names if n.startswith(".")])
    (dist / ".assets-manifest").write_text("\n".join(f.name for f in (dist / "assets").iterdir()))

og_image = next((f for f, _ in MEDIA if f.suffix.lower() in IMG), None)
OG_IMAGE = f'<meta property="og:image" content="{domain}/assets/{og_image.name}">' if og_image else ""

# ---- 지역 링크 (서울 / 그 외로 묶어서) --------------------------------------------------------
def group_of(r):
    return "서울" if r["city"].startswith("서울") else "경기·인천"

def region_links(prefix, current=None):
    groups = {}
    for r in regions:
        groups.setdefault(group_of(r), []).append(r)
    html = []
    for label, rs in groups.items():
        links = "".join(
            f'<a href="{prefix}{r["slug"]}/"{" class=on" if r is current else ""}>{r["name"]}</a>' for r in rs)
        html.append(f'<div class="rgroup"><b>{label}</b><div class="regions">{links}</div></div>')
    return "".join(html)

seoul_n = sum(1 for r in regions if group_of(r) == "서울")
others = [r["name"] for r in regions if group_of(r) != "서울"]
COVERAGE = "·".join(([f"서울 {seoul_n}개 구"] if seoul_n else []) + others)

def jsonld(url, area_served):
    d = {"@context": "https://schema.org", "@type": "LocalBusiness",
         "name": cfg["brand"], "telephone": cfg["phone"], "url": url,
         "areaServed": [{"@type": "Place", "name": a} for a in area_served]}
    if og_image:
        d["image"] = f"{domain}/assets/{og_image.name}"
    return j(d).replace("</", "<\\/")

def render(tpl, v):
    out = tpl
    for k, val in v.items():
        out = out.replace("{{" + k + "}}", val)
    left = re.findall(r"{{[A-Z_]+}}", out)
    if left: die(f"템플릿에 치환되지 않은 값이 있습니다: {sorted(set(left))}")
    return out

common = {"BRAND": cfg["brand"], "PHONE": cfg["phone"], "TELEGRAM": cfg["telegram"],
          "HOURS": cfg["hours"], "OG_IMAGE": OG_IMAGE}

# ---- 지역 페이지 -----------------------------------------------------------------------
urls = [f"{domain}/"]
for r in regions:
    url = f"{domain}/{r['slug']}/"
    urls.append(url)
    areas_text = "·".join(r["areas"])
    intro = r.get("intro") or f'{r["city"]} 자택·오피스텔로 전문 관리사가 직접 방문하는 홈케어. 선입금 없이 만나서 결제합니다.'
    v = {**common, "ROOT": "../", "URL": url,
         "REGION": r["name"], "CITY": r["city"], "AREAS_TEXT": areas_text, "INTRO": esc(intro),
         "AREA_CHIPS": "".join(f"<span>{a}</span>" for a in r["areas"]),
         "REGION_LINKS": region_links("../", r),
         "MEDIA": media_html("../"),
         "JSONLD": jsonld(url, [r["city"], *r["areas"]])}
    d = dist / r["slug"]; d.mkdir()
    (d / "index.html").write_text(render(tpl_region, v), encoding="utf-8")

# ---- 루트 허브: 코스 안내는 지역 템플릿의 <section id="courses">를 그대로 가져와 한 곳에서만 관리 ----
m = re.search(r'<section id="courses">.*?</section>', tpl_region, re.S)
courses = m.group(0) if m else ""
v = {**common, "ROOT": "", "URL": f"{domain}/", "COVERAGE": COVERAGE,
     "REGION_LINKS": region_links(""), "MEDIA": media_html(""), "COURSES": courses,
     "SLUGS_JSON": j([r["slug"] for r in regions]),
     "JSONLD": jsonld(f"{domain}/", [r["city"] for r in regions])}
(dist / "index.html").write_text(render(tpl_index, v), encoding="utf-8")

# ---- 공통 파일 -------------------------------------------------------------------------
shutil.copy2(root / "style.css", dist / "style.css")
(dist / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
(dist / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {domain}/sitemap.xml\n")
(dist / ".nojekyll").write_text("")

# 커스텀 도메인(github.io 가 아니고 하위 경로가 없을 때)이면 GitHub Pages 용 CNAME 생성
u = urlparse(domain)
if u.hostname and not u.hostname.endswith("github.io") and u.path in ("", "/"):
    (dist / "CNAME").write_text(u.hostname + "\n")

print(f"built {len(urls)} pages ({len(regions)} regions) -> dist/")
