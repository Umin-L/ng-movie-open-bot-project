"""
CGV 예매 가능 영화 체커 (Playwright 기반)

지점 미지정: /movies/ 페이지 렌더링 → 예매하기 버튼 있는 영화 추출
지점 지정:  /theaters/ 페이지 방문 → fetch/XHR 인터셉트 + 탭 클릭으로 지점 코드 수집
           → HTML 직접 파싱 폴백 (onclick, data-* 속성)
           → /common/showtimes/iframeTheater.aspx 로 지점별 상영 스케줄 파싱
"""

import re
from datetime import datetime, timedelta
from typing import List

from .base import BaseChecker, MovieInfo

CGV_MOVIES_URL   = "https://www.cgv.co.kr/movies/"
CGV_THEATERS_URL = "https://www.cgv.co.kr/theaters/"
CGV_SCHEDULE_URL = "https://www.cgv.co.kr/common/showtimes/iframeTheater.aspx"
CGV_DETAIL_BASE  = "https://www.cgv.co.kr/movies/detail.aspx?MovieSeq="

# fetch/XHR 인터셉터: 페이지 JS보다 먼저 주입하여 CGV 인증 요청까지 캡처
_INTERCEPT_SCRIPT = """
window.__cgv_captures = window.__cgv_captures || {};
try { Object.defineProperty(navigator,'webdriver',{get:function(){return undefined;},configurable:true}); } catch(e){}
(function() {
  try {
    var _f = window.fetch;
    window.fetch = async function() {
      var resp = await _f.apply(this, arguments);
      var url = (typeof arguments[0] === 'string' ? arguments[0]
                 : (arguments[0] && arguments[0].url)) || '';
      if (url.indexOf('cgv.co.kr') !== -1) {
        try { window.__cgv_captures[url] = await resp.clone().json(); } catch(e){}
      }
      return resp;
    };
  } catch(e){}
  try {
    var _xo = XMLHttpRequest.prototype.open;
    var _xs = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m, url) {
      this.__cgv_url = url; return _xo.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function() {
      this.addEventListener('load', function() {
        if (this.__cgv_url && this.__cgv_url.indexOf('cgv.co.kr') !== -1)
          try { window.__cgv_captures[this.__cgv_url] = JSON.parse(this.responseText); } catch(e){}
      });
      return _xs.apply(this, arguments);
    };
  } catch(e){}
})();
"""


class CGVChecker(BaseChecker):
    def get_bookable_movies(self, branches: List[str] = None, days_ahead: int = 0) -> List[MovieInfo]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[CGV] Playwright 미설치 — pip install playwright && playwright install chromium")
            return []

        if branches:
            return self._fetch_by_branches(branches, sync_playwright, days_ahead)
        return self._fetch_all(sync_playwright)

    # ── 지점 지정 없음: 전국 예매 가능 목록 ──────────────────────────
    def _fetch_all(self, sync_playwright) -> List[MovieInfo]:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent=self.HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
                )
                page.goto(CGV_MOVIES_URL, wait_until="networkidle", timeout=30000)
                html = page.content()
                browser.close()
            return self._parse_movies_page(html)
        except Exception as e:
            print(f"[CGV] 전체 조회 오류: {e}")
            return []

    # ── 지점 지정: 지점별 상영 스케줄 조회 (N일치) ──────────────────
    def _fetch_by_branches(self, branch_keywords: List[str], sync_playwright, days_ahead: int = 0) -> List[MovieInfo]:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                ctx = browser.new_context(
                    user_agent=self.HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
                    viewport={"width": 1280, "height": 800},
                )
                # webdriver 감지 우회 (configurable:true 로 재정의 허용)
                ctx.add_init_script(
                    "try{Object.defineProperty(navigator,'webdriver',{get:function(){return undefined;},configurable:true});}catch(e){}"
                )

                theaters = self._get_theaters_via_playwright(ctx, branch_keywords)
                if not theaters:
                    print(f"[CGV] 일치하는 지점 없음: {branch_keywords}")
                    browser.close()
                    return []

                dates = [
                    (datetime.now() + timedelta(days=d)).strftime("%Y%m%d")
                    for d in range(days_ahead + 1)
                ]

                movies = []
                seen = set()
                sched_page = ctx.new_page()

                for theater in theaters:
                    for date_str in dates:
                        url = (
                            f"{CGV_SCHEDULE_URL}"
                            f"?areacode={theater['area']}"
                            f"&theatercode={theater['code']}"
                            f"&date={date_str}"
                        )
                        try:
                            sched_page.goto(url, wait_until="networkidle", timeout=20000)
                            schedule_html = sched_page.content()
                            branch_movies = self._parse_schedule_page(
                                schedule_html, theater["name"], date_str
                            )
                            for m in branch_movies:
                                key = (m.title, m.branch, m.event_label, m.extra)
                                if key not in seen:
                                    seen.add(key)
                                    movies.append(m)
                        except Exception as e:
                            print(f"[CGV] {theater['name']} {date_str} 조회 오류: {e}")

                browser.close()
                return movies
        except Exception as e:
            print(f"[CGV] 지점별 조회 오류: {e}")
            return []

    # ── 지점 코드 조회 ───────────────────────────────────────────────
    def _get_theaters_via_playwright(self, ctx, branch_keywords: List[str]) -> List[dict]:
        """theaters 페이지에서 지점 코드를 수집한다.

        1순위: fetch/XHR 인터셉터로 searchRegnList API 응답 캡처
        2순위: HTML 파싱 (onclick 패턴 / data-* 속성)
        """
        page = ctx.new_page()
        theaters = []

        # 페이지 JS보다 먼저 인터셉터 주입 (webdriver 우회는 ctx에서 이미 처리)
        page.add_init_script(_INTERCEPT_SCRIPT)

        try:
            # /theaters/ 는 Oracle VM에서 에러 페이지 반환 → /movies/ 로 세션 확립
            page.goto(CGV_MOVIES_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)

            # ── 영화 페이지 컨텍스트에서 CGV API 직접 호출 ──────────────
            # (axios 사용 가능하면 axios 인터셉터로 X-Signature 자동 추가)
            result = page.evaluate("""async () => {
                var info = {
                    hasAxios: typeof axios !== 'undefined',
                    hasFetch: typeof fetch !== 'undefined',
                    cgvFuncs: Object.getOwnPropertyNames(window).filter(function(k){
                        return /cgv|api|theater|cinema|site|region/i.test(k);
                    }).slice(0, 20),
                };

                var REGION_URL = 'https://api.cgv.co.kr/cnm/site/searchAllRegionAndSite?coCd=A420';

                // 1) axios 시도
                if (typeof axios !== 'undefined') {
                    try {
                        var ar = await axios.get(REGION_URL);
                        info.axiosStatus = ar.status;
                        info.regions = ar.data && ar.data.data && ar.data.data.regionInfo;
                        return info;
                    } catch(e) {
                        info.axiosError = e.toString();
                    }
                }

                // 2) native fetch 시도
                try {
                    var r = await fetch(REGION_URL, { headers: { Accept: 'application/json' } });
                    info.fetchStatus = r.status;
                    if (r.ok) {
                        var d = await r.json();
                        info.regions = d.data && d.data.regionInfo;
                    } else {
                        info.fetchBody = await r.text();
                    }
                } catch(e) {
                    info.fetchError = e.toString();
                }
                return info;
            }""")

            print(f"[CGV] hasAxios={result.get('hasAxios')}, fetchStatus={result.get('fetchStatus')}, "
                  f"axiosStatus={result.get('axiosStatus')}")
            print(f"[CGV] fetchError={result.get('fetchError')}, axiosError={result.get('axiosError')}")
            print(f"[CGV] cgvFuncs={result.get('cgvFuncs')}")

            regions = result.get("regions") or []
            print(f"[CGV] 지역 수: {len(regions)}")

            # 지역별 지점 목록 조회
            for region in regions:
                area_code = region.get("comCdval", "")
                if not area_code:
                    continue
                sites_result = page.evaluate(f"""async () => {{
                    var url = 'https://api.cgv.co.kr/cnm/atkt/searchRegnList?coCd=A420&regnGrpCd={area_code}';
                    try {{
                        if (typeof axios !== 'undefined') {{
                            var r = await axios.get(url);
                            return r.data && r.data.data && r.data.data.siteList || [];
                        }}
                        var r = await fetch(url, {{ headers: {{ Accept: 'application/json' }} }});
                        if (!r.ok) return [];
                        var d = await r.json();
                        return d.data && d.data.siteList || [];
                    }} catch(e) {{ return []; }}
                }}""")
                for site in (sites_result or []):
                    name = site.get("siteNm", "")
                    code = site.get("siteNo", "")
                    if code and self.match_branch(name, branch_keywords):
                        theaters.append({"name": name, "area": area_code, "code": code})

        except Exception as e:
            print(f"[CGV] 지점 조회 실패: {e}")
        finally:
            page.close()
        return theaters

    def _parse_theaters_from_html(self, html: str, branch_keywords: List[str]) -> List[dict]:
        """theaters 페이지 HTML에서 지점 코드를 파싱한다 (폴백)."""
        from bs4 import BeautifulSoup
        theaters = []
        soup = BeautifulSoup(html, "lxml")

        # 패턴 1: data-theatercode / data-theater-code 속성
        for el in soup.select("[data-theatercode], [data-theater-code], [data-siteNo]"):
            name = el.get_text(strip=True)
            code = (el.get("data-theatercode")
                    or el.get("data-theater-code")
                    or el.get("data-siteNo", ""))
            area = (el.get("data-areacode")
                    or el.get("data-area-code", ""))
            if code and self.match_branch(name, branch_keywords):
                theaters.append({"name": name, "area": area, "code": code})

        # 패턴 2: onclick="...('areacode', 'theatercode')" 형식
        if not theaters:
            for el in soup.select("[onclick]"):
                onclick = el.get("onclick", "")
                m = re.search(r"['\"](\d{2})['\"].*?['\"](\d{4})['\"]", onclick)
                if m:
                    area, code = m.group(1), m.group(2)
                    name = el.get_text(strip=True)
                    if self.match_branch(name, branch_keywords):
                        theaters.append({"name": name, "area": area, "code": code})

        print(f"[CGV] HTML 파싱 결과: {len(theaters)}개")
        return theaters

    # ── 파싱 ────────────────────────────────────────────────────
    def _parse_movies_page(self, html: str) -> List[MovieInfo]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        movies = []

        for poster in soup.select("img[alt*='포스터'][src*='Poster']"):
            title = poster.get("alt", "").replace(" 포스터", "").strip()
            if not title:
                continue

            src = poster.get("src", "")
            code_match = re.search(r"/Poster/\d+/(\d+)/", src)
            movie_code = code_match.group(1) if code_match else ""
            booking_url = f"{CGV_DETAIL_BASE}{movie_code}" if movie_code else CGV_MOVIES_URL

            container = poster
            has_booking = False
            for _ in range(12):
                container = container.parent
                if container is None:
                    break
                if container.find("button", string=re.compile("예매하기")):
                    has_booking = True
                    break

            if has_booking:
                event_label = self._detect_event_label(container)
                movies.append(MovieInfo(
                    title=title,
                    theater="CGV",
                    booking_url=booking_url,
                    branch="",
                    extra="예매가능",
                    event_label=event_label,
                ))
        return movies

    # ── 이벤트 라벨 감지 ─────────────────────────────────────────────
    _EVENT_KEYWORDS = ["무대인사", "GV", "시사회", "무대 인사", "무대Q&A", "시네마톡"]

    def _detect_event_label(self, container) -> str:
        for sel in [
            ".badge-event", ".label-event", ".ico-event",
            "[class*='event']", "[class*='special']", "[class*='badge']",
            ".tag", ".ico-imax", "em.ico",
        ]:
            for tag in container.select(sel):
                text = tag.get_text(strip=True)
                for kw in self._EVENT_KEYWORDS:
                    if kw in text:
                        return kw
        container_text = container.get_text()
        for kw in self._EVENT_KEYWORDS:
            if kw in container_text:
                return kw
        return ""

    def _parse_schedule_page(self, html: str, branch_name: str, date_str: str = "") -> List[MovieInfo]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        movies = []

        for li in soup.select(".sect-showtimes ul li, ul.list-schedule li"):
            title_tag = li.select_one(
                "div.col-times div.info-movie a strong, .tit-movie strong, strong.title"
            )
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue

            time_items = li.select("div.info-timetable ul li")
            has_available = any(
                "not-sale" not in " ".join(t.get("class", []))
                for t in time_items
            ) if time_items else True

            if has_available:
                event_label = self._detect_event_label(li)
                movies.append(MovieInfo(
                    title=title,
                    theater="CGV",
                    booking_url=CGV_MOVIES_URL,
                    branch=branch_name,
                    extra="예매가능",
                    event_label=event_label,
                    play_date=date_str,
                ))
        return movies
