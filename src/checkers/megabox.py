"""
메가박스 예매 가능 영화 체커

지점 미지정: selectMovieList.do → 전국 예매 가능 영화 목록
지점 지정:  schedulePage.do  → 해당 지점의 실제 상영 스케줄 기반
"""

import json
from datetime import datetime
from typing import List, Optional

import requests

from .base import BaseChecker, MovieInfo

MEGABOX_MOVIE_LIST_URL = "https://www.megabox.co.kr/on/oh/oha/Movie/selectMovieList.do"
MEGABOX_SCHEDULE_URL = "https://www.megabox.co.kr/on/oh/ohc/Brch/schedulePage.do"
MEGABOX_DETAIL_BASE = "https://www.megabox.co.kr/movie/detail"


class MegaboxChecker(BaseChecker):
    def get_bookable_movies(self, branches: List[str] = None) -> List[MovieInfo]:
        if branches:
            return self._fetch_by_branches(branches)
        return self._fetch_all()

    # ── 지점 지정 없음: 전국 예매 가능 목록 ──────────────────────────
    def _fetch_all(self) -> List[MovieInfo]:
        headers = {
            **self.HEADERS,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.megabox.co.kr/movie",
        }
        movies: List[MovieInfo] = []
        page = 1

        while True:
            payload = {
                "currentPage": str(page),
                "recordCountPerPage": "100",
                "pageType": "list",
                "ibxMovieNmSearch": "",
                "onairYn": "",
                "specialType": "",
                "specialYn": "N",
            }
            try:
                resp = requests.post(
                    MEGABOX_MOVIE_LIST_URL,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[메가박스] 전체 조회 실패 (page={page}): {e}")
                break

            items = data.get("movieList", [])
            if not items:
                break

            total = int(items[0].get("totCnt", 0))
            for item in items:
                title = item.get("movieNm", "").strip()
                if not title or item.get("bokdAbleYn") != "Y":
                    continue
                movie_no = item.get("movieNo", "")
                rel_date = item.get("rfilmDe", "")
                stat_nm = item.get("movieStatNm", "")
                booking_url = (
                    f"{MEGABOX_DETAIL_BASE}?movieNo={movie_no}"
                    if movie_no
                    else "https://www.megabox.co.kr/booking"
                )
                movies.append(
                    MovieInfo(
                        title=title,
                        theater="메가박스",
                        booking_url=booking_url,
                        branch="",
                        extra=f"예매가능 | {stat_nm} | 개봉: {rel_date}",
                    )
                )

            if len(movies) >= total or len(items) < 100:
                break
            page += 1

        return movies

    # ── 지점 지정: 오늘 스케줄 기반 ────────────────────────────────
    def _fetch_by_branches(self, branch_keywords: List[str]) -> List[MovieInfo]:
        headers = {
            **self.HEADERS,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.megabox.co.kr/booking/timetable",
        }
        today = datetime.now().strftime("%Y%m%d")

        try:
            resp = requests.post(
                MEGABOX_SCHEDULE_URL,
                data=json.dumps({"masterType": "brch", "playDe": today}),
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            schedules = resp.json().get("megaMap", {}).get("movieFormList", [])
        except Exception as e:
            print(f"[메가박스] 지점별 스케줄 조회 실패: {e}")
            return []

        movies: List[MovieInfo] = []
        seen = set()

        for item in schedules:
            brch_nm = item.get("brchNm", "")
            if not self.match_branch(brch_nm, branch_keywords):
                continue

            title = item.get("rpstMovieNm") or item.get("movieNm", "")
            title = title.strip()
            if not title:
                continue

            bokd = item.get("bokdAbleAt", "N")
            if bokd != "Y":
                continue

            # 이벤트 라벨 추출 (무대인사, GV, 시사회 등)
            event_label = item.get("eventDivCdNm", "").strip()
            event_progrs = item.get("eventProgrs", "").strip()
            if event_label and event_progrs:
                event_label = f"{event_label}({event_progrs})"

            key = (title, brch_nm, event_label)
            if key in seen:
                continue
            seen.add(key)

            movie_no = item.get("movieNo", "")
            stat_nm = item.get("movieStatCdNm", "")
            booking_url = (
                f"{MEGABOX_DETAIL_BASE}?movieNo={movie_no}"
                if movie_no
                else "https://www.megabox.co.kr/booking"
            )
            extra = f"예매가능 | {stat_nm}"
            movies.append(
                MovieInfo(
                    title=title,
                    theater="메가박스",
                    booking_url=booking_url,
                    branch=brch_nm,
                    extra=extra,
                    event_label=event_label,
                )
            )

        return movies
