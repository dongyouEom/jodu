#!/usr/bin/env python3
"""regions.json + template.html -> dist/index.html  (python3 build.py)
지역 전환은 페이지 안 JS가 처리 (탭 클릭 또는 #Slug 해시). 기본 표시는 첫 지역."""
import json, pathlib, shutil

root = pathlib.Path(__file__).parent
cfg = json.loads((root / "regions.json").read_text(encoding="utf-8"))
tpl = (root / "template.html").read_text(encoding="utf-8")
dist = root / "dist"

# dist/assets/ 에 직접 넣은 파일은 빌드 때 지워지므로, 원본 assets/ 로 옮겨 살린다.
# (이전 빌드가 복사한 파일 목록은 dist/.assets-manifest 에 있고, 그 목록에 없는 파일만 구한다)
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
assets = root / "assets"
IMG = {".gif", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg"}
VID = {".mp4", ".webm"}

def media_html():
    """assets/ 의 이미지·GIF·영상을 갤러리 섹션으로. regions.json의 media에 적은 순서·캡션 우선,
    media가 없으면 assets/ 전체를 파일명 순으로 자동 수록."""
    if not assets.is_dir():
        return ""
    items = cfg.get("media")
    if items is None:
        items = [{"file": f.name} for f in sorted(assets.iterdir()) if f.suffix.lower() in IMG | VID]
    figs = []
    for it in items:
        f = assets / it["file"]
        if not f.is_file():
            print(f"skip (없음): assets/{it['file']}"); continue
        cap = it.get("caption", "")
        if f.suffix.lower() in VID:
            tag = f'<video src="assets/{f.name}" autoplay muted loop playsinline></video>'
        else:
            tag = f'<img src="assets/{f.name}" alt="{cap}" loading="lazy">'
        figs.append(f"<figure>{tag}{f'<figcaption>{cap}</figcaption>' if cap else ''}</figure>")
    if not figs:
        return ""
    shutil.copytree(assets, dist / "assets", ignore=lambda d, names: [n for n in names if n.startswith(".")])
    (dist / ".assets-manifest").write_text("\n".join(f.name for f in (dist / "assets").iterdir()))
    return '  <section>\n    <div class="gallery">' + "".join(figs) + "</div>\n  </section>"
first = cfg["regions"][0]
j = lambda x: json.dumps(x, ensure_ascii=False)
v = {
    "BRAND": cfg["brand"], "PHONE": cfg["phone"], "TELEGRAM": cfg["telegram"],
    "DOMAIN": domain, "HOURS": cfg["hours"],
    # JS 비활성/크롤러용 초기값 = 첫 지역
    "REGION": first["name"], "CITY": first["city"],
    "AREAS_TEXT": "·".join(first["areas"]),
    "AREA_CHIPS": "".join(f"<span>{a}</span>" for a in first["areas"]),
    "REGION_LINKS": "".join(
        f'<a href="#{r["slug"]}" data-slug="{r["slug"]}"{" class=on" if r is first else ""}>{r["name"]}</a>'
        for r in cfg["regions"]),
    "REGIONS_JSON": j(cfg["regions"]).replace("</", "<\\/"),
    "BRAND_JSON": j(cfg["brand"]), "HOURS_JSON": j(cfg["hours"]),
    "MEDIA": media_html(),
}
out = tpl
for k, val in v.items():
    out = out.replace("{{" + k + "}}", val)
(dist / "index.html").write_text(out, encoding="utf-8")

(dist / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    f"<url><loc>{domain}/</loc></url></urlset>", encoding="utf-8")
(dist / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {domain}/sitemap.xml\n")
print(f"built 1 page ({len(cfg['regions'])} regions) -> dist/index.html")
