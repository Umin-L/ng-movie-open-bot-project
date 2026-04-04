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
CGV_SCHEDULE_URL    = "https://www.cgv.co.kr/common/showtimes/"
CGV_DETAIL_BASE     = "https://www.cgv.co.kr/movies/detail.aspx?MovieSeq="
CGV_SCN_API         = "https://api.cgv.co.kr/cnm/atkt/searchMovScnInfo"

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
    """
    CGV 예매 가능 영화 체커.
    지점별 스케줄 API가 Cloudflare로 차단되어 있어,
    /movies/ 페이지 전역 크롤링으로 이벤트 라벨(무대인사/GV 등) 감지.
    """

    def get_bookable_movies(self, branches: List[str] = None, days_ahead: int = 0) -> List[MovieInfo]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[CGV] Playwright 미설치")
            return []

        if branches:
            print("[CGV] 지점별 API 차단 → 전역 이벤트 감지 모드")

        return self._fetch_all(sync_playwright)

    @staticmethod
    def _get_proxy() -> str:
        import os
        return os.environ.get("CGV_PROXY_URL", "")

    def _fetch_all(self, sync_playwright) -> List[MovieInfo]:
        proxy_url = self._get_proxy()
        pw_proxy = {"server": proxy_url} if proxy_url else None

        try:
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
                print("[CGV] mets01081 에러 페이지")
                return []
            return self._parse_movies_page(html)
        except Exception as e:
            print(f"[CGV] 조회 오류: {e}")
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
            code_match = re.search(r"[Pp]oster[%2F/]+\d+[%2F/]+(\d+)", src)
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
