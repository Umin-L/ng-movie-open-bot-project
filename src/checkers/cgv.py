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
window.__cgv_captures = {};
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
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent=self.HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
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

        # 페이지 JS보다 먼저 인터셉터 주입
        page.add_init_script(_INTERCEPT_SCRIPT)

        try:
            page.goto(CGV_THEATERS_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)

            # ── 페이지 구조 디버그 ──────────────────────────────────
            info = page.evaluate("""() => {
                var html = document.documentElement.innerHTML;
                return {
                    len: html.length,
                    hasTheaterCode: html.indexOf('theatercode') !== -1 || html.indexOf('theaterCode') !== -1,
                    hasSiteNo: html.indexOf('siteNo') !== -1,
                    hasAreaCode: html.indexOf('areacode') !== -1 || html.indexOf('areaCode') !== -1,
                    captureKeys: Object.keys(window.__cgv_captures),
                    areaTabCount: document.querySelectorAll(
                        'ul.list-area>li, #ulArea>li, .area-tab li, [class*="area"]>li'
                    ).length,
                };
            }""")
            print(f"[CGV] 페이지 정보: HTML길이={info.get('len')}, "
                  f"theatercode={info.get('hasTheaterCode')}, siteNo={info.get('hasSiteNo')}, "
                  f"areaCode={info.get('hasAreaCode')}, 캡처={info.get('captureKeys')}, "
                  f"지역탭={info.get('areaTabCount')}")

            # ── 지역 탭 클릭 시도 ──────────────────────────────────
            tab_selectors = [
                "ul.list-area > li",
                "#ulArea > li",
                ".area-tab li",
                "div.wrap-theater-area li",
                "[class*='list-area'] li",
                "a[onclick*='area'], li[onclick*='area']",
            ]
            clicked = 0
            for sel in tab_selectors:
                els = page.query_selector_all(sel)
                if els:
                    print(f"[CGV] 지역 탭 셀렉터 '{sel}': {len(els)}개")
                    for el in els:
                        try:
                            el.click()
                            page.wait_for_timeout(600)
                            clicked += 1
                        except Exception:
                            pass
                    break  # 첫 번째로 일치하는 셀렉터만 사용

            if clicked:
                page.wait_for_timeout(1000)

            # ── 1순위: 인터셉터 캡처 결과 처리 ──────────────────────
            captures = page.evaluate("() => window.__cgv_captures")
            print(f"[CGV] 캡처된 API 수: {len(captures)}")
            for c_url, data in captures.items():
                print(f"[CGV]   - {c_url[:80]}")
                if "searchRegnList" in c_url:
                    m = re.search(r'regnGrpCd=([^&]+)', c_url)
                    area_code = m.group(1) if m else ""
                    for site in (data.get("data", {}).get("siteList", []) or []):
                        name = site.get("siteNm", "")
                        code = site.get("siteNo", "")
                        if code and self.match_branch(name, branch_keywords):
                            theaters.append({"name": name, "area": area_code, "code": code})

            # ── 2순위: HTML 직접 파싱 ─────────────────────────────
            if not theaters:
                print("[CGV] 인터셉터 캡처 없음 → HTML 파싱 시도")
                html = page.content()
                theaters = self._parse_theaters_from_html(html, branch_keywords)

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
