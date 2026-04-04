"""
CGV 예매 가능 영화 체커 (Playwright 기반)

지점 미지정: /movies/ 페이지 렌더링 → 예매하기 버튼 있는 영화 추출
지점 지정:  정적 지점 DB에서 키워드 매칭 → 지점 코드 확보
           → /common/showtimes/iframeTheater.aspx 로 지점별 상영 스케줄 파싱
"""

import re
from datetime import datetime, timedelta
from typing import List

from .base import BaseChecker, MovieInfo

CGV_MOVIES_URL      = "https://www.cgv.co.kr/movies/"
CGV_MOBILE_URL      = "https://m.cgv.co.kr/WebApp/MovieV4/MovieList.aspx"
CGV_SCHEDULE_URL    = "https://www.cgv.co.kr/common/showtimes/iframeTheater.aspx"
CGV_DETAIL_BASE     = "https://www.cgv.co.kr/movies/detail.aspx?MovieSeq="

# ── 전국 CGV 지점 정적 DB (2026-04 기준) ──────────────────────────────────
# api.cgv.co.kr 가 Oracle Cloud IP에서 차단되므로 정적으로 내장
_CGV_THEATERS = [
    # 서울 (01)
    {"area": "01", "code": "0056", "name": "강남"},
    {"area": "01", "code": "0001", "name": "강변"},
    {"area": "01", "code": "0229", "name": "건대입구"},
    {"area": "01", "code": "0366", "name": "고덕강일"},
    {"area": "01", "code": "0010", "name": "구로"},
    {"area": "01", "code": "0063", "name": "대학로"},
    {"area": "01", "code": "0252", "name": "동대문"},
    {"area": "01", "code": "0230", "name": "등촌"},
    {"area": "01", "code": "0009", "name": "명동"},
    {"area": "01", "code": "0057", "name": "미아"},
    {"area": "01", "code": "0288", "name": "방학"},
    {"area": "01", "code": "0030", "name": "불광"},
    {"area": "01", "code": "0046", "name": "상봉"},
    {"area": "01", "code": "0300", "name": "성신여대입구"},
    {"area": "01", "code": "0276", "name": "수유"},
    {"area": "01", "code": "0150", "name": "신촌아트레온"},
    {"area": "01", "code": "P001", "name": "씨네드쉐프 압구정"},
    {"area": "01", "code": "P013", "name": "씨네드쉐프 용산"},
    {"area": "01", "code": "0040", "name": "압구정"},
    {"area": "01", "code": "0112", "name": "여의도"},
    {"area": "01", "code": "0292", "name": "연남"},
    {"area": "01", "code": "0059", "name": "영등포타임스퀘어"},
    {"area": "01", "code": "0074", "name": "왕십리"},
    {"area": "01", "code": "0013", "name": "용산아이파크몰"},
    {"area": "01", "code": "0131", "name": "중계"},
    {"area": "01", "code": "0199", "name": "천호"},
    {"area": "01", "code": "0107", "name": "청담씨네시티"},
    {"area": "01", "code": "0223", "name": "피카디리1958"},
    {"area": "01", "code": "0191", "name": "홍대"},
    # 경기 (02)
    {"area": "02", "code": "0260", "name": "경기광주"},
    {"area": "02", "code": "0270", "name": "고양백석"},
    {"area": "02", "code": "0374", "name": "고양행신"},
    {"area": "02", "code": "0257", "name": "광교"},
    {"area": "02", "code": "0266", "name": "광교상현"},
    {"area": "02", "code": "0348", "name": "광명역"},
    {"area": "02", "code": "0232", "name": "구리"},
    {"area": "02", "code": "0358", "name": "구리갈매"},
    {"area": "02", "code": "0344", "name": "기흥"},
    {"area": "02", "code": "0278", "name": "김포"},
    {"area": "02", "code": "0188", "name": "김포운양"},
    {"area": "02", "code": "0298", "name": "김포한강"},
    {"area": "02", "code": "0329", "name": "남양주화도"},
    {"area": "02", "code": "0351", "name": "다산"},
    {"area": "02", "code": "0236", "name": "동두천"},
    {"area": "02", "code": "0124", "name": "동백"},
    {"area": "02", "code": "0041", "name": "동수원"},
    {"area": "02", "code": "0106", "name": "동탄"},
    {"area": "02", "code": "0359", "name": "동탄그랑파사쥬"},
    {"area": "02", "code": "0265", "name": "동탄역"},
    {"area": "02", "code": "0233", "name": "동탄호수공원"},
    {"area": "02", "code": "0226", "name": "배곧"},
    {"area": "02", "code": "0155", "name": "범계"},
    {"area": "02", "code": "0015", "name": "부천"},
    {"area": "02", "code": "0194", "name": "부천역"},
    {"area": "02", "code": "0242", "name": "산본"},
    {"area": "02", "code": "0196", "name": "서현"},
    {"area": "02", "code": "0143", "name": "소풍"},
    {"area": "02", "code": "0274", "name": "스타필드시티위례"},
    {"area": "02", "code": "0055", "name": "신세계경기"},
    {"area": "02", "code": "0211", "name": "안산"},
    {"area": "02", "code": "0279", "name": "안성"},
    {"area": "02", "code": "0003", "name": "야탑"},
    {"area": "02", "code": "0262", "name": "양주옥정"},
    {"area": "02", "code": "0338", "name": "역곡"},
    {"area": "02", "code": "0004", "name": "오리"},
    {"area": "02", "code": "0307", "name": "오산중앙"},
    {"area": "02", "code": "0271", "name": "용인"},
    {"area": "02", "code": "0113", "name": "의정부"},
    {"area": "02", "code": "0205", "name": "이천"},
    {"area": "02", "code": "0054", "name": "일산"},
    {"area": "02", "code": "0148", "name": "파주문산"},
    {"area": "02", "code": "0371", "name": "파주운정"},
    {"area": "02", "code": "0181", "name": "판교"},
    {"area": "02", "code": "0195", "name": "평촌"},
    {"area": "02", "code": "0052", "name": "평택"},
    {"area": "02", "code": "0334", "name": "평택고덕"},
    {"area": "02", "code": "0214", "name": "평택소사"},
    {"area": "02", "code": "0309", "name": "포천"},
    {"area": "02", "code": "0301", "name": "화성봉담"},
    {"area": "02", "code": "0145", "name": "화정"},
    {"area": "02", "code": "0365", "name": "Drive In 용인 크랙사이드"},
    # 인천 (03)
    {"area": "03", "code": "0043", "name": "계양"},
    {"area": "03", "code": "0021", "name": "부평"},
    {"area": "03", "code": "0325", "name": "송도타임스페이스"},
    {"area": "03", "code": "0002", "name": "인천"},
    {"area": "03", "code": "0296", "name": "인천가정"},
    {"area": "03", "code": "0340", "name": "인천도화"},
    {"area": "03", "code": "0352", "name": "인천시민공원"},
    {"area": "03", "code": "0258", "name": "인천연수"},
    {"area": "03", "code": "0269", "name": "인천학익"},
    {"area": "03", "code": "0308", "name": "주안역"},
    {"area": "03", "code": "0235", "name": "청라"},
    # 강원 (04)
    {"area": "04", "code": "0139", "name": "강릉"},
    {"area": "04", "code": "0355", "name": "기린"},
    {"area": "04", "code": "0354", "name": "원통"},
    {"area": "04", "code": "0281", "name": "인제"},
    {"area": "04", "code": "0070", "name": "춘천"},
    # 대전/충청 (05)
    {"area": "05", "code": "0370", "name": "논산"},
    {"area": "05", "code": "0207", "name": "당진"},
    {"area": "05", "code": "0007", "name": "대전"},
    {"area": "05", "code": "0286", "name": "대전가수원"},
    {"area": "05", "code": "0154", "name": "대전가오"},
    {"area": "05", "code": "0202", "name": "대전탄방"},
    {"area": "05", "code": "0127", "name": "대전터미널"},
    {"area": "05", "code": "0091", "name": "서산"},
    {"area": "05", "code": "0219", "name": "세종"},
    {"area": "05", "code": "0356", "name": "아산"},
    {"area": "05", "code": "0206", "name": "유성노은"},
    {"area": "05", "code": "0369", "name": "천안"},
    {"area": "05", "code": "0293", "name": "천안터미널"},
    {"area": "05", "code": "0110", "name": "천안펜타포트"},
    {"area": "05", "code": "0228", "name": "청주(서문)"},
    {"area": "05", "code": "0142", "name": "청주지웰시티"},
    {"area": "05", "code": "0319", "name": "청주터미널"},
    {"area": "05", "code": "0284", "name": "충북혁신"},
    {"area": "05", "code": "0328", "name": "충주교현"},
    {"area": "05", "code": "0217", "name": "홍성"},
    # 대구 (06)
    {"area": "06", "code": "0345", "name": "대구"},
    {"area": "06", "code": "0108", "name": "대구스타디움"},
    {"area": "06", "code": "0343", "name": "대구연경"},
    {"area": "06", "code": "0216", "name": "대구월성"},
    {"area": "06", "code": "0256", "name": "대구죽전"},
    {"area": "06", "code": "0147", "name": "대구한일"},
    {"area": "06", "code": "0109", "name": "대구현대"},
    # 부산/울산 (07)
    {"area": "07", "code": "0061", "name": "대연"},
    {"area": "07", "code": "0042", "name": "동래"},
    {"area": "07", "code": "0337", "name": "부산명지"},
    {"area": "07", "code": "0005", "name": "서면"},
    {"area": "07", "code": "0285", "name": "서면삼정타워"},
    {"area": "07", "code": "0303", "name": "서면상상마당"},
    {"area": "07", "code": "0089", "name": "센텀시티"},
    {"area": "07", "code": "P004", "name": "씨네드쉐프 센텀"},
    {"area": "07", "code": "0160", "name": "아시아드"},
    {"area": "07", "code": "0335", "name": "울산동구"},
    {"area": "07", "code": "0128", "name": "울산삼산"},
    {"area": "07", "code": "0333", "name": "울산성남"},
    {"area": "07", "code": "0264", "name": "울산신천"},
    {"area": "07", "code": "0246", "name": "울산진장"},
    {"area": "07", "code": "0306", "name": "정관"},
    {"area": "07", "code": "0245", "name": "하단아트몰링"},
    {"area": "07", "code": "0318", "name": "해운대"},
    {"area": "07", "code": "0367", "name": "Drive In 영도"},
    # 경상 (08)
    {"area": "08", "code": "0263", "name": "거제"},
    {"area": "08", "code": "0330", "name": "경산"},
    {"area": "08", "code": "0323", "name": "고성"},
    {"area": "08", "code": "0053", "name": "구미"},
    {"area": "08", "code": "0240", "name": "김천율곡"},
    {"area": "08", "code": "0028", "name": "김해"},
    {"area": "08", "code": "0311", "name": "김해율하"},
    {"area": "08", "code": "0239", "name": "김해장유"},
    {"area": "08", "code": "0033", "name": "마산"},
    {"area": "08", "code": "0097", "name": "북포항"},
    {"area": "08", "code": "0272", "name": "안동"},
    {"area": "08", "code": "0234", "name": "양산삼호"},
    {"area": "08", "code": "0324", "name": "진주혁신"},
    {"area": "08", "code": "0079", "name": "창원더시티"},
    {"area": "08", "code": "0283", "name": "창원상남"},
    # 광주/전라/제주 (09)
    {"area": "09", "code": "0220", "name": "광양"},
    {"area": "09", "code": "0221", "name": "광양 엘에프스퀘어"},
    {"area": "09", "code": "0295", "name": "광주금남로"},
    {"area": "09", "code": "0193", "name": "광주상무"},
    {"area": "09", "code": "0210", "name": "광주용봉"},
    {"area": "09", "code": "0218", "name": "광주첨단"},
    {"area": "09", "code": "0244", "name": "광주충장로"},
    {"area": "09", "code": "0215", "name": "광주하남"},
    {"area": "09", "code": "0237", "name": "나주"},
    {"area": "09", "code": "0280", "name": "목포평화광장"},
    {"area": "09", "code": "0225", "name": "서전주"},
    {"area": "09", "code": "0268", "name": "순천신대"},
    {"area": "09", "code": "0315", "name": "여수웅천"},
    {"area": "09", "code": "0020", "name": "익산"},
    {"area": "09", "code": "0213", "name": "전주고사"},
    {"area": "09", "code": "0336", "name": "전주에코시티"},
    {"area": "09", "code": "0179", "name": "전주효자"},
    {"area": "09", "code": "0186", "name": "정읍"},
    {"area": "09", "code": "0302", "name": "제주"},
    {"area": "09", "code": "0259", "name": "제주노형"},
]


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

    @staticmethod
    def _get_proxy() -> str:
        """환경변수 CGV_PROXY_URL에서 프록시 URL 반환. 예: socks5://localhost:1080"""
        import os
        return os.environ.get("CGV_PROXY_URL", "")

    # ── 지점 지정 없음: 전국 예매 가능 목록 ──────────────────────────
    def _fetch_all(self, sync_playwright) -> List[MovieInfo]:
        proxy_url = self._get_proxy()
        if proxy_url:
            print(f"[CGV] 프록시 사용: {proxy_url}")

        # Playwright로 JS 렌더링 (프록시 지원)
        try:
            pw_proxy = {"server": proxy_url} if proxy_url else None
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, proxy=pw_proxy)
                page = browser.new_page(
                    user_agent=self.HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
                )
                page.goto(CGV_MOVIES_URL, wait_until="networkidle", timeout=30000)
                html = page.content()
                browser.close()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            if soup.select_one(".mets01081_Case2, .errorPage"):
                print(f"[CGV] Playwright: mets01081 에러 페이지 (HTML길이={len(html)})")
                return []
            movies = self._parse_movies_page(html)
            print(f"[CGV] Playwright 파싱 완료: {len(movies)}개")
            return movies
        except Exception as e:
            print(f"[CGV] Playwright 조회 오류: {e}")
            return []

    # ── 지점 지정: Playwright + 프록시로 iframeTheater.aspx 조회 ──────
    def _fetch_by_branches(self, branch_keywords: List[str], sync_playwright, days_ahead: int = 0) -> List[MovieInfo]:
        matched = [t for t in _CGV_THEATERS if self.match_branch(t["name"], branch_keywords)]
        if not matched:
            print(f"[CGV] 일치하는 지점 없음: {branch_keywords}")
            return []
        print(f"[CGV] 대상 지점: {sorted(t['name'] for t in matched)}")

        dates = [
            (datetime.now() + timedelta(days=d)).strftime("%Y%m%d")
            for d in range(days_ahead + 1)
        ]

        proxy_url = self._get_proxy()
        pw_proxy = {"server": proxy_url} if proxy_url else None

        movies = []
        seen: set = set()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, proxy=pw_proxy)
                ctx = browser.new_context(
                    user_agent=self.HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
                )
                # CGV 메인 페이지 워밍업 (쿠키/세션 확보)
                page = ctx.new_page()
                page.goto(CGV_MOVIES_URL, wait_until="domcontentloaded", timeout=30000)

                for theater in matched:
                    for date_str in dates:
                        url = (
                            f"{CGV_SCHEDULE_URL}"
                            f"?TheaterCode={theater['code']}&date={date_str}"
                        )
                        try:
                            # 브라우저 쿠키를 재사용하는 경량 HTTP 요청
                            resp = ctx.request.get(url, timeout=15000)
                            html = resp.text()
                            if len(html) < 3000:
                                print(f"[CGV] {theater['name']} {date_str}: HTML 짧음({len(html)}), 스킵")
                                continue
                            branch_movies = self._parse_schedule_page(html, theater["name"], date_str)
                            for m in branch_movies:
                                key = (m.title, m.branch, m.event_label, m.play_date)
                                if key not in seen:
                                    seen.add(key)
                                    movies.append(m)
                        except Exception as e:
                            print(f"[CGV] {theater['name']} {date_str} 오류: {e}")

                browser.close()
        except Exception as e:
            print(f"[CGV] Playwright 브라우저 오류: {e}")

        return movies

    def _parse_movie_schedule(self, html: str, title: str, event_label: str,
                               branch_names: set, date_str: str) -> List[MovieInfo]:
        """iframeMovie.aspx: 특정 영화의 전국 상영 목록에서 대상 지점 필터링."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        movies = []

        # 상영관(지점) 목록에서 이름 파싱 후 branch_names 매칭
        for theater_section in soup.select(".sect-showtimes, .theater-info, [class*='theater']"):
            name_tag = theater_section.select_one(
                ".theater-name, .tit-theater, h3, h4, strong, .name"
            )
            if not name_tag:
                continue
            theater_name = name_tag.get_text(strip=True)
            # branch_names 중 하나라도 theater_name에 포함되는지 확인
            if not any(bn in theater_name or theater_name in bn for bn in branch_names):
                continue

            time_items = theater_section.select("div.info-timetable ul li, .timetable li")
            has_available = any(
                "not-sale" not in " ".join(t.get("class", []))
                for t in time_items
            ) if time_items else True

            if has_available:
                movies.append(MovieInfo(
                    title=title,
                    theater="CGV",
                    booking_url=CGV_MOVIES_URL,
                    branch=theater_name,
                    extra="예매가능",
                    event_label=event_label,
                    play_date=date_str,
                ))
        return movies

    # ── 파싱 ────────────────────────────────────────────────────
    def _parse_movies_page(self, html: str) -> List[MovieInfo]:
        from bs4 import BeautifulSoup
        from collections import Counter
        soup = BeautifulSoup(html, "lxml")
        movies = []

        # 디버그: 페이지 구조 파악
        imgs_poster_alt = soup.select("img[alt*='포스터']")
        imgs_poster_src = soup.select("img[src*='Poster']")
        imgs_all = soup.select("img[src*='cgv']")
        print(f"[CGV] img[alt*포스터]={len(imgs_poster_alt)}, img[src*Poster]={len(imgs_poster_src)}, img[src*cgv]={len(imgs_all)}")
        if imgs_all:
            s = imgs_all[0]
            print(f"[CGV] 첫 img src={s.get('src','')[:100]}, alt={s.get('alt','')[:50]}")
        all_classes = []
        for el in soup.find_all(True):
            cls = el.get("class")
            if cls:
                all_classes.extend(cls)
        top15 = [c for c, _ in Counter(all_classes).most_common(15)]
        print(f"[CGV] 상위클래스: {top15}")

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

    def _parse_mobile_movies(self, html: str) -> List[MovieInfo]:
        """CGV 모바일 사이트에서 예매 가능 영화 파싱."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        movies = []

        # mets01081 에러 페이지 감지
        if soup.select_one(".mets01081_Case2, .errorPage"):
            print("[CGV] 모바일도 mets01081 에러 페이지")
            return []

        # 모바일 영화 목록: 다양한 셀렉터 시도
        items = (
            soup.select(".sect-movie-list li")
            or soup.select(".movie-list li")
            or soup.select("ul.list-movie li")
            or soup.select(".movie-item")
            or soup.select("li.item")
        )
        print(f"[CGV] 모바일 영화 항목 수: {len(items)}")

        for item in items:
            title_tag = (
                item.select_one(".title-wrap .title")
                or item.select_one(".tit-movie")
                or item.select_one("strong.title")
                or item.select_one(".movie-name")
            )
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue

            # 예매 버튼 / 링크 확인
            booking_tag = (
                item.select_one("a[href*='ticketing'], a[href*='booking'], a.btn-booking")
                or item.select_one("button.btn-booking, a.btn-reserve")
            )
            # 예매 불가 표시 없으면 예매 가능으로 간주
            sold_out = item.select_one(".sold-out, .not-sale, .dday-box.end")
            if sold_out:
                continue

            # 영화 코드 추출
            code_tag = item.select_one("a[href*='MovieSeq='], a[href*='movieseq=']")
            movie_code = ""
            if code_tag:
                href = code_tag.get("href", "")
                m = re.search(r"[Mm]ovie[Ss]eq=(\w+)", href)
                if m:
                    movie_code = m.group(1)
            booking_url = f"{CGV_DETAIL_BASE}{movie_code}" if movie_code else CGV_MOVIES_URL

            event_label = self._detect_event_label(item)
            movies.append(MovieInfo(
                title=title,
                theater="CGV",
                booking_url=booking_url,
                branch="",
                extra="예매가능",
                event_label=event_label,
            ))

        return movies

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
        for kw in self._EVENT_KEYWORDS:
            if kw in container.get_text():
                return kw
        return ""

    def _parse_schedule_page(self, html: str, branch_name: str, date_str: str = "") -> List[MovieInfo]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        movies = []

        # 디버그: 파싱 구조 확인 (추후 제거)
        all_els = soup.select("li, article, div.movie, .item")
        print(f"[CGV:{branch_name}] HTML길이={len(html)}, 전체li/article={len(all_els)}")
        if len(html) < 500 or not all_els:
            print(f"[CGV:{branch_name}] HTML미리보기: {html[:800]}")
        else:
            # 실제 구조 파악용 - 첫 번째 의미있는 클래스 목록 출력
            classes = []
            for el in soup.find_all(True):
                cls = el.get("class")
                if cls:
                    classes.extend(cls)
            from collections import Counter
            top = [c for c, _ in Counter(classes).most_common(20)]
            print(f"[CGV:{branch_name}] 상위 클래스: {top}")

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
