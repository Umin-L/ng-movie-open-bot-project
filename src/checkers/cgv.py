"""
CGV 예매 가능 영화 체커 (Playwright 기반)

지점 미지정: /movies/ 페이지 렌더링 → 예매하기 버튼 있는 영화 추출
지점 지정:  /theaters/ 페이지에서 지점 코드 조회
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
CGV_REGION_API    = "https://api.cgv.co.kr/cnm/site/searchAllRegionAndSite?coCd=A420"
CGV_SITE_API      = "https://api.cgv.co.kr/cnm/atkt/searchRegnList?coCd=A420"


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

                # 1. Playwright 컨텍스트 안에서 API로 지점 목록 조회
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

                for theater in theaters:
                    for date_str in dates:
                        url = (
                            f"{CGV_SCHEDULE_URL}"
                            f"?areacode={theater['area']}"
                            f"&theatercode={theater['code']}"
                            f"&date={date_str}"
                        )
                        try:
                            page.goto(url, wait_until="networkidle", timeout=20000)
                            schedule_html = page.content()
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
        """CGV 지점 페이지 로드 시 네트워크 응답 인터셉트로 지점 목록 수집."""
        page = ctx.new_page()
        theaters = []
        captured: list = []

        def on_response(response):
            if "searchRegnList" in response.url:
                try:
                    data = response.json()
                    area_code = str(response.url).split("regnGrpCd=")[-1].split("&")[0] if "regnGrpCd=" in response.url else ""
                    sites = data.get("data", {}).get("siteList", [])
                    captured.append((area_code, sites))
                except Exception:
                    pass

        page.on("response", on_response)
        try:
            page.goto(CGV_THEATERS_URL, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"[CGV] 지점 페이지 로드 실패: {e}")
        finally:
            page.close()

        for area_code, sites in captured:
            for site in sites:
                name = site.get("siteNm", "")
                code = site.get("siteNo", "")
                if code and self.match_branch(name, branch_keywords):
                    theaters.append({"name": name, "area": area_code, "code": code})

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
