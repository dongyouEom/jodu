#!/usr/bin/env python3
"""regions.json + template*.html -> dist/  (python3 build.py)

dist/index.html          루트(허브): 브랜드 소개 + 전체 지역 목록
dist/<slug>/index.html   지역별 페이지 (검색엔진이 지역마다 별도 URL로 색인)
dist/style.css, assets/, sitemap.xml, robots.txt, (커스텀 도메인이면) CNAME
"""
import hashlib, json, pathlib, re, shutil, subprocess
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
FFMPEG, FFPROBE = shutil.which("ffmpeg"), shutil.which("ffprobe")
if MEDIA and not FFMPEG:
    print("참고: ffmpeg 없음 -> GIF/이미지 변환 생략, 원본 그대로 사용 (GitHub Actions에서는 자동 변환됨)")

def run(*args):
    try:
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        return True
    except Exception as e:
        print(f"변환 실패 ({args[-1]}): {e}"); return False

def probe(path):
    """(width, height) 또는 None. CLS 방지용 width/height 속성에 쓴다."""
    if not FFPROBE: return None
    try:
        out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=width,height", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=60).stdout.strip().split(",")
        return int(out[0]), int(out[1])
    except Exception:
        return None

if MEDIA:
    shutil.copytree(assets, dist / "assets", ignore=lambda d, names: [n for n in names if n.startswith(".")])

def prepare_media():
    """GIF -> mp4(+포스터 jpg), png/jpg -> webp 로 변환해 dist/assets 에 추가. 실패·ffmpeg 없음이면 원본 사용.
    반환: [{kind, src, fallback, poster, w, h, cap}]"""
    out_dir = dist / "assets"
    items = []
    for f, cap in MEDIA:
        ext = f.suffix.lower(); stem = f.stem
        it = {"kind": "img", "src": f.name, "fallback": None, "poster": None, "cap": cap}
        dims = probe(f)
        if ext == ".gif" and FFMPEG:
            mp4, jpg = out_dir / f"{stem}.mp4", out_dir / f"{stem}.jpg"
            ok = run(FFMPEG, "-y", "-loglevel", "error", "-i", str(f), "-an", "-movflags", "+faststart",
                     "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(mp4))
            if ok:
                it.update(kind="video", src=mp4.name, fallback=f.name)
                if run(FFMPEG, "-y", "-loglevel", "error", "-i", str(f), "-frames:v", "1", "-q:v", "3", str(jpg)):
                    it["poster"] = jpg.name
                dims = probe(mp4) or dims
        elif ext in {".png", ".jpg", ".jpeg"} and FFMPEG:
            webp = out_dir / f"{stem}.webp"
            if run(FFMPEG, "-y", "-loglevel", "error", "-i", str(f), "-c:v", "libwebp", "-quality", "82", str(webp)):
                it.update(kind="picture", src=webp.name, fallback=f.name)
        elif ext in VID:
            it["kind"] = "video"
        if dims: it["w"], it["h"] = dims
        items.append(it)
    if items:
        (dist / ".assets-manifest").write_text("\n".join(f.name for f in out_dir.iterdir()))
    return items

ITEMS = prepare_media() if MEDIA else []

def media_html(prefix):
    figs = []
    for it in ITEMS:
        a = f"{prefix}assets/"
        wh = f' width="{it["w"]}" height="{it["h"]}"' if it.get("w") else ""
        cap = esc(it["cap"])
        if it["kind"] == "video":
            poster = f' poster="{a}{it["poster"]}"' if it.get("poster") else ""
            tag = (f'<video src="{a}{it["src"]}"{poster}{wh} autoplay muted loop playsinline preload="metadata" aria-label="{cap}">'
                   + (f'<img src="{a}{it["fallback"]}" alt="{cap}" loading="lazy">' if it.get("fallback") else "") + "</video>")
        elif it["kind"] == "picture":
            tag = (f'<picture><source srcset="{a}{it["src"]}" type="image/webp">'
                   f'<img src="{a}{it["fallback"]}" alt="{cap}"{wh} loading="lazy"></picture>')
        else:
            tag = f'<img src="{a}{it["src"]}" alt="{cap}"{wh} loading="lazy">'
        figs.append(f"<figure>{tag}{f'<figcaption>{cap}</figcaption>' if cap else ''}</figure>")
    if not figs:
        return ""
    return '  <section>\n    <div class="gallery">' + "".join(figs) + "</div>\n  </section>"

def og_image_name():
    """og:image 는 정지 이미지가 안전: 포스터 jpg > webp 변환 원본 > 첫 이미지."""
    for it in ITEMS:
        if it.get("poster"): return it["poster"]
        if it["kind"] == "picture": return it["fallback"]
        if it["kind"] == "img" and pathlib.Path(it["src"]).suffix.lower() in IMG: return it["src"]
    return None

og_image = og_image_name()
OG_IMAGE = f'<meta property="og:image" content="{domain}/assets/{og_image}">' if og_image else ""

# 검색엔진 소유권 인증 메타 태그 (regions.json "verify": {"google": "코드"}), 값이 있을 때만 출력
VERIFY_META = "".join(
    f'<meta name="{k}-site-verification" content="{esc(v)}">\n'
    for k, v in (cfg.get("verify") or {}).items() if v)

# ---- 상위(구·시) / 하위(동·역) 지역 --------------------------------------------------------
# "parent": 상위 지역 slug. 하위 지역은 자기 페이지를 갖되 지역 목록에는 넣지 않고,
# 상위 페이지에서만 링크한다 ("인계동 출장마사지" 같은 좁은 검색어를 잡기 위한 페이지).
by_slug = {r["slug"]: r for r in regions}
children = {}
for r in regions:
    p = r.get("parent")
    if not p:
        continue
    if p not in by_slug: die(f'{r["name"]}의 "parent" slug "{p}"에 해당하는 지역이 없습니다.')
    if by_slug[p].get("parent"): die(f'"parent"는 한 단계만 가능합니다: {r["slug"]} -> {p}')
    children.setdefault(p, []).append(r)

def group_of(r):
    if r.get("parent"):
        r = by_slug[r["parent"]]
    return r.get("group") or ("서울" if r["city"].startswith("서울") else "경기·인천")

def region_links(prefix, current=None, collapse_to=None):
    """collapse_to 묶음만 펼쳐두고 나머지는 접는다 (선택된 지역을 다시 누르면 JS가 펼침)."""
    groups = {}
    for r in regions:
        if r.get("parent"):
            continue
        groups.setdefault(group_of(r), []).append(r)
    html = []
    for label, rs in groups.items():
        links = "".join(
            f'<a href="{prefix}{r["slug"]}/"{" class=on" if r is current else ""}>{r["name"]}</a>' for r in rs)
        off = " off" if collapse_to and label != collapse_to else ""
        html.append(f'<div class="rgroup{off}"><b>{label}</b><div class="regions">{links}</div></div>')
    return "".join(html)

# 제목·설명에 들어가므로 지역이 많아지면 regions.json 의 "coverage" 로 짧게 고정한다
seoul_n = sum(1 for r in regions if group_of(r) == "서울")
others = [r["name"] for r in regions if group_of(r) != "서울"]
COVERAGE = cfg.get("coverage") or "·".join(([f"서울 {seoul_n}개 구"] if seoul_n else []) + others)

def jsonld(url, area_served, geo=None):
    d = {"@context": "https://schema.org", "@type": "LocalBusiness",
         "name": cfg["brand"], "telephone": cfg["phone"], "url": url,
         "areaServed": [{"@type": "Place", "name": a} for a in area_served]}
    if geo:
        d["geo"] = {"@type": "GeoCoordinates", "latitude": geo[0], "longitude": geo[1]}
    if og_image:
        d["image"] = f"{domain}/assets/{og_image}"
    return j(d).replace("</", "<\\/")

def sub_links(r, prefix="../"):
    """상위 지역이면 하위 지역 목록을, 하위 지역이면 상위 지역과 형제 지역을 링크한다."""
    kids = children.get(r["slug"])
    if kids:
        label, items, cur = f'{r["name"]} 주요 지역', kids, None
    elif r.get("parent"):
        parent = by_slug[r["parent"]]
        label, items, cur = f'{parent["name"]} 전체', [parent, *children[parent["slug"]]], r
    else:
        return ""
    links = "".join(f'<a href="{prefix}{x["slug"]}/"{" class=on" if x is cur else ""}>{x["name"]}</a>'
                    for x in items)
    return f'    <div class="rgroup"><b>{label}</b><div class="regions">{links}</div></div>\n'

def map_html(r):
    """번화가 좌표 지도. 스크롤해 내려와야 로드되도록 lazy."""
    g = r.get("geo")
    if not g:
        return ""
    return (f'<div class="map"><iframe title="{esc(r["name"])} 위치" loading="lazy" allowfullscreen '
            f'referrerpolicy="no-referrer-when-downgrade" '
            f'src="https://maps.google.com/maps?q={g[0]},{g[1]}&amp;z=14&amp;output=embed"></iframe></div>')

FAQ_SRC = re.findall(r"<details><summary>(.*?)</summary><p>(.*?)</p></details>", tpl_region, re.S)

def faq_jsonld(v):
    """FAQ 섹션(template.html)의 질문·답변을 지역값으로 치환해 FAQPage JSON-LD 로. 원본은 템플릿 한 곳."""
    def sub(t):
        for k, val in v.items(): t = t.replace("{{" + k + "}}", val)
        return re.sub(r"<[^>]+>", "", t).strip()
    if not FAQ_SRC: return ""
    d = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": sub(q), "acceptedAnswer": {"@type": "Answer", "text": sub(a)}} for q, a in FAQ_SRC]}
    return '<script type="application/ld+json">' + j(d).replace("</", "<\\/") + "</script>"

def render(tpl, v):
    out = tpl
    for k, val in v.items():
        out = out.replace("{{" + k + "}}", val)
    left = re.findall(r"{{[A-Z_]+}}", out)
    if left: die(f"템플릿에 치환되지 않은 값이 있습니다: {sorted(set(left))}")
    return out

# style.css 를 고쳐도 브라우저가 옛 파일을 계속 쓰지 않도록 내용 해시를 쿼리로 붙인다
CSS_V = hashlib.sha1((root / "style.css").read_bytes()).hexdigest()[:8]

common = {"BRAND": cfg["brand"], "PHONE": cfg["phone"], "TELEGRAM": cfg["telegram"],
          "HOURS": cfg["hours"], "OG_IMAGE": OG_IMAGE, "VERIFY_META": VERIFY_META, "CSS_V": CSS_V}

# ---- 카드 문구 변형: 지역마다 완전히 같은 문장이 반복되지 않도록 slug 해시로 고정 선택 -------
# (매 빌드마다 바뀌면 diff가 커지고 캐시도 깨지므로, slug+슬롯명 해시로 "항상 같은 지역엔 같은 문구"가 나오게 고정한다)
CARD1_P1 = [
    "{region}출장마사지는 다양한 분들이 찾으십니다. 바쁜 직장인, 출장 중이신 분, 스트레스와 불면증에 시달리는 분 등 여러 경우가 있습니다. 원하시는 장소에서 편안하게 관리를 받고 싶은 분들이 선택하는 서비스입니다.",
    "{region}출장마사지를 찾는 이유는 다양합니다. 야근이 잦은 직장인, 타지에서 출장 중이신 분, 잠들기 어려울 만큼 몸이 무거운 분까지 저마다의 사정으로 연락 주십니다. 계신 자리에서 편하게 관리받고 싶은 분들이 주로 이용합니다.",
    "{region}에서 출장마사지를 부르는 분들의 이유는 제각각입니다. 매일 야근에 지친 직장인부터 낯선 곳에서 숙박 중인 출장자, 만성 피로와 불면에 시달리는 분까지 폭넓습니다. 원하는 장소로 편하게 방문받고 싶은 분들이 선택하는 서비스입니다.",
    "{region}출장마사지는 바쁜 일상에 지친 분들이 많이 찾습니다. 잦은 야근, 타지 출장, 스트레스성 불면 등 이유는 다양하지만 공통적으로 원하시는 곳에서 편하게 관리받길 원하십니다.",
    "{region}에는 다양한 이유로 출장마사지를 찾는 분들이 있습니다. 격무에 시달리는 직장인, 출장 중이신 분, 스트레스·불면으로 힘든 분까지. 계신 곳에서 편안히 관리받고 싶은 분들이 선택하는 서비스입니다.",
]
CARD1_P2 = [
    "<b>20·30대 전문 한국인 관리사와 태국인 관리사</b>가 직접 방문합니다. 지금 계신 그곳에서 편하고 안전하게 퀄리티 높은 출장 관리를 받으실 수 있습니다. <b>착한 가격, 최적가로 정성껏 모시겠습니다.</b>",
    "<b>20·30대 한국인 관리사와 태국인 관리사</b>가 직접 찾아갑니다. 계신 장소에서 안전하고 편안하게 퀄리티 높은 관리를 받으실 수 있으며, <b>합리적인 가격으로 정성껏 모시겠습니다.</b>",
    "<b>전문 교육을 받은 20·30대 한국인·태국인 관리사</b>가 방문합니다. 어디에 계시든 안전하고 편안한 환경에서 퀄리티 높은 관리를 받으실 수 있고, <b>부담 없는 가격으로 모시겠습니다.</b>",
    "<b>검증된 20·30대 한국인 관리사와 태국인 관리사</b>가 직접 방문합니다. 계신 자리에서 안전하게, 높은 퀄리티로 관리받으실 수 있습니다. <b>합리적인 가격, 최적가로 응대하겠습니다.</b>",
    "<b>20·30대 한국인·태국인 전문 관리사</b>가 직접 찾아뵙니다. 안전하고 편안한 환경에서 퀄리티 높은 관리를 받으실 수 있으며, <b>착한 가격으로 정성껏 모시겠습니다.</b>",
]
CARD2_P1 = [
    "{region}출장마사지는 예약금 없는 신뢰로 영업합니다. {city}에서 검증된 관리사만 배정하며 <b>선입금·예약금을 일체 요구하지 않습니다.</b>",
    "{region}출장마사지는 예약금 없이 신뢰로만 운영합니다. {city} 내 검증된 관리사만 배정하며 <b>선입금이나 예약금은 절대 요구하지 않습니다.</b>",
    "{region}에서는 예약금 없는 방식으로 영업합니다. {city} 소재 검증된 관리사만 배정하고 <b>선입금·예약금 요구는 일절 없습니다.</b>",
    "{region}출장마사지는 선입금 없는 신뢰 영업이 원칙입니다. {city}에서 활동하는 검증된 관리사만 배정하며 <b>예약금은 받지 않습니다.</b>",
    "{region}에서 신뢰를 최우선으로 운영합니다. {city}에서 검증을 마친 관리사만 배정하며 <b>선입금·예약금은 전혀 요구하지 않습니다.</b>",
]
CARD2_P2 = [
    "과도한 업무로 피로가 쌓여 몸이 무거우실 때, 힐링이 필요하실 때 저희를 불러주세요. 타이 홈타이 관리사의 시원한 손맛을 느껴보세요.",
    "업무에 지쳐 몸이 무겁고 힐링이 필요하실 때 편하게 연락 주세요. 시원한 손맛의 타이 홈타이 관리를 경험해보실 수 있습니다.",
    "쌓인 피로로 몸이 무겁고 쉬고 싶으실 때 불러주세요. 손끝이 시원한 타이 홈타이 관리사가 방문해드립니다.",
    "격무에 지친 몸, 힐링이 간절하실 때 언제든 연락 주세요. 시원한 손맛을 가진 타이 홈타이 관리사를 만나보세요.",
    "피로가 쌓여 몸이 무겁거나 힐링이 필요하실 때 저희를 찾아주세요. 시원한 손맛의 타이 홈타이 관리를 받아보실 수 있습니다.",
]
INTRO_FALLBACK = [
    "{a0} 상권과 {a1} 일대까지 전문 관리사가 직접 방문합니다. {city} 어디든 이동 동선이 짧아 예약 후 빠르게 도착합니다. 선입금 없이 만나서 결제합니다.",
    "{a0}부터 {a1}까지 {city} 전 지역을 관리사가 직접 찾아갑니다. 대기 인원이 많아 늦은 시간에도 배정이 빠른 편입니다. 선입금 없이 만나서 결제합니다.",
    "{a0} 인근과 {a1} 일대 원룸·오피스텔까지 빠짐없이 방문합니다. {city} 어디든 30분 내외로 도착하도록 관리사를 배정합니다. 선입금 없이 만나서 결제합니다.",
    "{a0}·{a1} 등 {city} 전 지역에 전문 관리사가 방문합니다. 이동 동선이 짧아 예약 후 대기 시간이 길지 않습니다. 선입금 없이 만나서 결제합니다.",
    "{a0} 생활권과 {a1} 인근까지 {city} 전역을 관리사가 직접 방문합니다. 예약이 몰리는 시간에도 빠르게 배정해드립니다. 선입금 없이 만나서 결제합니다.",
]

def pick(slug, slot, variants):
    """지역 slug + 슬롯명을 해시해 변형 문구를 고정 선택 (같은 지역은 재빌드해도 항상 같은 문구)."""
    h = int(hashlib.md5(f"{slug}:{slot}".encode()).hexdigest(), 16)
    return variants[h % len(variants)]

# ---- 지역 페이지 -----------------------------------------------------------------------
urls = [f"{domain}/"]
for r in regions:
    url = f"{domain}/{r['slug']}/"
    urls.append(url)
    areas_text = "·".join(r["areas"])
    intro = r.get("intro") or pick(r["slug"], "intro", INTRO_FALLBACK).format(
        a0=r["areas"][0], a1=r["areas"][1], city=r["city"])
    fmt = {"region": r["name"], "city": r["city"]}
    v = {**common, "ROOT": "../", "URL": url,
         "REGION": r["name"], "CITY": r["city"], "AREAS_TEXT": areas_text, "INTRO": esc(intro),
         "CARD1_P1": pick(r["slug"], "card1_p1", CARD1_P1).format(**fmt),
         "CARD1_P2": pick(r["slug"], "card1_p2", CARD1_P2).format(**fmt),
         "CARD2_P1": pick(r["slug"], "card2_p1", CARD2_P1).format(**fmt),
         "CARD2_P2": pick(r["slug"], "card2_p2", CARD2_P2).format(**fmt),
         "REGION_LINKS": region_links("../", r),
         "REGION_LINKS_TOP": region_links("../", by_slug.get(r.get("parent"), r), collapse_to=group_of(r)),
         "SUB_LINKS": sub_links(r),
         "MEDIA": media_html("../"), "MAP": map_html(r),
         "JSONLD": jsonld(url, [r["city"], *r["areas"]], r.get("geo"))}
    v["FAQ_JSONLD"] = faq_jsonld(v)
    d = dist / r["slug"]; d.mkdir()
    (d / "index.html").write_text(render(tpl_region, v), encoding="utf-8")

# ---- 루트 허브: 지역과 무관한 섹션은 지역 템플릿에서 그대로 가져와 한 곳에서만 관리 ----
def section_of(sid):
    m = re.search(rf'<section id="{sid}">.*?</section>', tpl_region, re.S)
    return m.group(0) if m else ""

v = {**common, "ROOT": "", "URL": f"{domain}/", "COVERAGE": COVERAGE,
     "REGION_LINKS": region_links(""), "MEDIA": media_html(""),
     "COURSES": section_of("courses"), "EVENTS": section_of("events"), "NOTICE": section_of("notice"),
     "SLUGS_JSON": j([r["slug"] for r in regions]),
     "JSONLD": jsonld(f"{domain}/", [r["city"] for r in regions])}
(dist / "index.html").write_text(render(tpl_index, v), encoding="utf-8")

# ---- 공통 파일 -------------------------------------------------------------------------
shutil.copy2(root / "style.css", dist / "style.css")
# 파비콘: icons/ 의 파일을 사이트 루트로 (/favicon.ico 는 브라우저·검색엔진이 기본으로 찾는 경로)
for f in (root / "icons").iterdir():
    if f.is_file():
        shutil.copy2(f, dist / f.name)
# lastmod: 페이지 내용에 영향을 주는 소스의 마지막 커밋 날짜 (검색엔진 재수집 신호). git이 없으면 생략
try:
    lastmod = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "template.html", "template-index.html",
                              "regions.json", "style.css", "assets", "icons"],
                             cwd=root, capture_output=True, text=True, check=True).stdout.strip()
except (OSError, subprocess.CalledProcessError):
    lastmod = ""
lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
(dist / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"  <url><loc>{u}</loc>{lm}</url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
(dist / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {domain}/sitemap.xml\n")
(dist / ".nojekyll").write_text("")

# 커스텀 도메인(github.io 가 아니고 하위 경로가 없을 때)이면 GitHub Pages 용 CNAME 생성
u = urlparse(domain)
if u.hostname and not u.hostname.endswith("github.io") and u.path in ("", "/"):
    (dist / "CNAME").write_text(u.hostname + "\n")

print(f"built {len(urls)} pages ({len(regions)} regions) -> dist/")
