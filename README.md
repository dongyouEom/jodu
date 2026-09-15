# jodu

지역별 랜딩 페이지 정적 생성기. 의존성 없음 (python3만).

```
python3 build.py          # dist/ 생성
python3 -m http.server -d dist 8000   # 로컬 확인 → http://localhost:8000/#Sillim
```

- `regions.json` — 업체명·전화·텔레그램 링크·도메인·지역 목록·갤러리 파일 목록.
  - 지역 추가는 `regions`에 한 줄.
  - `telegram`은 `https://t.me/아이디` 형태.
- `assets/` — 갤러리에 올릴 이미지·GIF·영상(gif/png/jpg/webp/avif/svg/mp4/webm).
  파일을 넣고 `regions.json`의 `media`에 `{ "file": "파일명", "caption": "설명" }`을 추가하면
  히어로 아래·코스 안내 위에 표시된다. `media` 항목을 통째로 지우면 `assets/` 전체가 파일명 순으로 자동 수록된다.
  `assets/example.gif`는 자리 확인용 예시이니 실제 파일로 교체하면 된다.
- `template.html` — 페이지 1장 템플릿. `{{BRAND}}` 같은 공통 값은 빌드 시 치환되고,
  지역별 값(`data-r="name|city|areas|chips"`)은 페이지 안 JS가 선택된 지역으로 채운다.
- 지역 선택 — 상단/하단 지역 탭 클릭, 또는 URL 해시 `#Sillim` `#Incheon` `#Songtan`.
  해시가 없거나 잘못되면 첫 지역을 표시. JS 미동작 시에도 첫 지역 내용은 HTML에 그대로 있음.
- `dist/` — 배포 결과물(index.html, assets/, sitemap.xml, robots.txt). Cloudflare Pages / GitHub Pages / Netlify에 폴더째 올리면 끝.
