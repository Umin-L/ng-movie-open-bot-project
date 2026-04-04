"""
CGV 예매 가능 영화 체커 (Playwright 기반)

지점 미지정: /movies/ 페이지 렌더링 → 예매하기 버튼 있는 영화 추출
지점 지정:  /theaters/ 페이지 방문 → 네트워크 인터셉트로 지점 코드 수집
           → 지역탭 클릭으로 미수집 지역 보완
           → /common/showtimes/iframeTheater.aspx 로 지점별 상영 스케줄 파싱
"""

import re
from datetime import datetime, timedelta
from typing import List

from .base import BaseChecker, MovieInfo

CGV_MOVIES_URL    = "https://www.cgv.co.kr/movies/"
CGV_THEATERS_URL  = "https://www.cgv.co.kr/theaters/"
CGV_SCHEDULE_URL  = "https://www.cgv.co.kr/common/showtimes/iframeTheater.aspx"
CGV_DETAIL_BASE   = "https://www.cgv.co.kr/movies/detail.aspx?MovieSeq="


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

                # 1. 지점 목록 조회 (theaters 페이지 네트워크 인터셉트)
                theaters = self._get_theaters_via_playwright(ctx, branch_keywords)
                if not theaters:
                    print(f"[CGV] 일치하는 지점 없음: {branch_keywords}")
                    browser.close()
                    return []

                # 2. 날짜 목록 생성 (오늘 ~ days_ahead 일 후)
                dates = [
                    (datetime.now() + timedelta(days=d)).strftime("%Y%m%d")
                    for d in range(days_ahead + 1)
                ]

                movies = []
                seen = set()

                # 3. 스케줄 조회용 페이지 생성
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

            # 부모 컨테이너에 "예매하기" 버튼 유무 확인
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

    def _get_theaters_via_playwright(self, ctx, branch_keywords: List[str]) -> List[dict]:
        """CGV theaters 페이지 네트워크 인터셉트로 지점 코드 수집.

        CGV API는 X-Signature 헤더를 요구하므로, 페이지 자체 JS가 호출하는
        API 응답을 인터셉트하는 방식을 사용한다.
        """
        page = ctx.new_page()
        theaters = []
        regions_data = []
        sites_by_area: dict = {}

        def on_response(response):
            try:
                url = response.url
                if "searchAllRegionAndSite" in url:
                    d = response.json()
                    for r in (d.get("data", {}).get("regionInfo", []) or []):
                        regions_data.append(r)
                elif "searchRegnList" in url:
                    m = re.search(r'regnGrpCd=([^&]+)', url)
                    area_code = m.group(1) if m else ""
                    d = response.json()
                    if area_code:
                        sites_by_area[area_code] = d.get("data", {}).get("siteList", [])
            except Exception:
                pass

        page.on("response", on_response)

        try:
            # theaters 페이지: 자동으로 searchAllRegionAndSite 호출
            page.goto(CGV_THEATERS_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            print(f"[CGV] 지역 목록: {len(regions_data)}개, 수집된 지역 데이터: {len(sites_by_area)}개")

            # 인터셉트로 수집 안 된 지역: 탭 클릭으로 보완
            for region in regions_data:
                area_code = region.get("comCdval", "")
                if area_code in sites_by_area:
                    continue
                # 여러 셀렉터 시도
                clicked = False
                for sel in [
                    f"[data-areacode='{area_code}']",
                    f"[data-area='{area_code}']",
                    f"li[onclick*=\"'{area_code}'\"]",
                    f"a[href*='areacode={area_code}']",
                    f"button[value='{area_code}']",
                ]:
                    el = page.query_selector(sel)
                    if el:
                        el.click()
                        page.wait_for_timeout(600)
                        clicked = True
                        break
                if not clicked:
                    # JS evaluate 로 직접 클릭 이벤트 발생
                    page.evaluate(f"""() => {{
                        const els = document.querySelectorAll('[class*="area"], [class*="region"], [id*="area"]');
                        for (const el of els) {{
                            if (el.textContent.includes('{region.get("comCdNm", "")}')) {{
                                el.click(); break;
                            }}
                        }}
                    }}""")
                    page.wait_for_timeout(600)

            page.wait_for_timeout(1000)
            print(f"[CGV] 탭 클릭 후 지역 데이터: {len(sites_by_area)}개")

            # 지점 매칭
            for area_code, sites in sites_by_area.items():
                for site in sites:
                    name = site.get("siteNm", "")
                    code = site.get("siteNo", "")
                    if code and self.match_branch(name, branch_keywords):
                        theaters.append({"name": name, "area": area_code, "code": code})

        except Exception as e:
            print(f"[CGV] 지점 조회 실패: {e}")
        finally:
            page.close()
        return theaters

    # ── 이벤트 라벨 감지 ─────────────────────────────────────────────
    _EVENT_KEYWORDS = ["무대인사", "GV", "시사회", "무대 인사", "무대Q&A", "시네마톡"]

    def _detect_event_label(self, container) -> str:
        """컨테이너 HTML에서 이벤트 라벨(무대인사/GV/시사회)을 감지한다."""
        # 1. 전용 뱃지/태그 요소 탐색
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
        # 2. 컨테이너 전체 텍스트 폴백
        container_text = container.get_text()
        for kw in self._EVENT_KEYWORDS:
            if kw in container_text:
                return kw
        return ""

    def _parse_schedule_page(self, html: str, branch_name: str, date_str: str = "") -> List[MovieInfo]:
        """CGV iframeTheater 상영시간표 페이지에서 영화 목록 파싱."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        movies = []

        date_display = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if date_str else ""

        # 상영시간표 구조: .sect-showtimes > ul > li
        for li in soup.select(".sect-showtimes ul li, ul.list-schedule li"):
            title_tag = li.select_one(
                "div.col-times div.info-movie a strong, .tit-movie strong, strong.title"
            )
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue

            # 예매 가능한 시간대가 하나라도 있으면 포함 (클래스 not 'not-sale')
            time_items = li.select("div.info-timetable ul li")
            has_available = any(
                "not-sale" not in " ".join(t.get("class", []))
                for t in time_items
            ) if time_items else True  # 시간표 없으면 일단 포함

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
