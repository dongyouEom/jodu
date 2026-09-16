# jodu

지역별 랜딩 페이지 정적 생성기. 의존성 없음 (python3만).

## 비개발자용: 브라우저에서 수정하면 자동 배포

1. 지역·문구·텔레그램 링크 수정 → GitHub에서 `regions.json` 열고 연필(Edit) → 수정 → **Commit changes**
2. 이미지·GIF 추가 → `assets` 폴더에서 **Add file → Upload files** → 올리고 Commit
   → 그 다음 `regions.json`의 `media`에 `{ "file": "올린파일명", "caption": "설명" }` 한 줄 추가
3. 1~2분 후 사이트 자동 갱신 (Actions 탭에서 진행 상황 확인). 빌드·푸시 불필요.

## 개발자용: 로컬 빌드

```
python3 build.py          # dist/ 생성
python3 -m http.server -d dist 8000   # 로컬 확인 → http://localhost:8000/  ,  /gangnam/
```

- `regions.json` — 업체명·전화·텔레그램 링크·도메인·운영시간·지역 목록·갤러리 파일 목록.
  - 지역 추가는 `regions`에 한 줄. `slug`는 영문 소문자(URL 경로 `/gangnam/`이 됨). 한 번 배포된 slug는 바꾸지 않는다(색인이 깨짐).
  - `group`: 지역 묶음 이름(예: "경기 북부"). 없으면 `city`가 "서울"로 시작할 때 서울, 아니면 "경기·인천". 지역 페이지 상단에는 같은 묶음만 보이고 "전체 지역 보기"로 펼친다.
  - `intro`: 지역별 소개 문장(없으면 기본 문장). 기본 문장은 지역명만 바뀌어 중복 콘텐츠로 취급되기 쉬우니, 주력 지역부터 그 지역에만 해당하는 내용으로 쓴다.
  - `geo`: `[위도, 경도]` 번화가 좌표. 구조화 데이터의 위치와 "방문 가능 지역" 아래 지도에 쓰인다. 없으면 지도 생략.
  - `coverage`: 루트 페이지 제목·설명에 들어가는 짧은 서비스 지역 문구.
  - `telegram`은 `https://t.me/아이디` 형태. `domain`을 바꾸면 canonical·sitemap·robots·CNAME이 자동 반영.
  - `verify.google` / `verify.naver`에 HTML 태그 인증 코드를 넣으면 모든 페이지 `<head>`에 메타 태그가 들어간다. 비워두면 출력 안 함 (Search Console을 DNS TXT로 인증했다면 불필요).
  - 항목 누락·slug 중복 등은 빌드가 한국어 메시지로 실패시킴 (Actions 로그에서 확인).
- `assets/` — 갤러리에 올릴 이미지·GIF·영상(gif/png/jpg/webp/avif/svg/mp4/webm).
  파일을 넣고 `regions.json`의 `media`에 `{ "file": "파일명", "caption": "설명" }`을 추가하면
  히어로 아래·코스 안내 위에 표시된다. `media`를 `[]`로 두면 갤러리를 아예 출력하지 않고,
  `media` 항목을 통째로 지우면 `assets/` 전체가 파일명 순으로 자동 수록된다.
  빌드 시 ffmpeg가 있으면 GIF는 mp4(+포스터 jpg)로, png/jpg는 webp로 자동 변환해 가볍게 내보낸다
  (GitHub Actions에는 항상 있음, 로컬은 `brew install ffmpeg`). 없으면 원본 그대로 사용.
- `template.html` — 지역 페이지 1장 템플릿. `{{REGION}}` 같은 값은 빌드 시 지역마다 치환된다.
  코스 안내·할인 이벤트·유의사항(`<section id="courses">`, `id="events"`, `id="notice"`)은 여기서만 고치면 루트 페이지에도 같이 반영.
  이 id를 바꾸면 루트 페이지에서 해당 섹션이 사라지고, 이 섹션 안에는 `{{REGION}}` 같은 지역 값을 넣으면 안 된다.
  자주 묻는 질문(`<details>`)은 빌드 시 FAQPage 구조화 데이터(JSON-LD)로도 자동 출력되므로 질문·답변은 여기 한 곳만 수정.
- `template-index.html` — 루트(허브) 페이지 템플릿. 브랜드 소개 + 전체 지역 목록.
- `style.css` — 두 템플릿이 공유하는 스타일. 맨 위 `:root` 색상 변수를 지우면 버튼 색이 전부 사라진다.
  빌드가 파일 해시를 `style.css?v=…`로 붙이므로 수정 즉시 방문자에게 반영된다(HTML은 GitHub Pages가 10분 캐시).
- 지역 페이지 — 지역마다 `/<slug>/` 별도 HTML로 생성되어 검색엔진이 각각 색인한다 (예: `/gangnam/`).
  예전 `#Slug` 해시 주소로 들어오면 루트에서 해당 지역 페이지로 이동.
- `dist/` — 배포 결과물(index.html, <slug>/index.html, style.css, assets/, sitemap.xml, robots.txt, CNAME). 직접 고치지 말고 소스를 고쳐 재빌드.
  GitHub Actions 배포에서는 CNAME 파일만으로 커스텀 도메인이 설정되지 않으니 저장소 Settings → Pages → Custom domain에 직접 입력해야 한다.
