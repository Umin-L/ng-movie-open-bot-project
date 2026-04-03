"""
메가박스 예매 가능 영화 체커

지점 미지정: selectMovieList.do → 전국 예매 가능 영화 목록
지점 지정:  schedulePage.do  → 해당 지점의 실제 상영 스케줄 기반
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional

import requests

from .base import BaseChecker, MovieInfo

MEGABOX_MOVIE_LIST_URL = "https://www.megabox.co.kr/on/oh/oha/Movie/selectMovieList.do"
MEGABOX_SCHEDULE_URL = "https://www.megabox.co.kr/on/oh/ohc/Brch/schedulePage.do"
MEGABOX_DETAIL_BASE = "https://www.megabox.co.kr/movie/detail"


class MegaboxChecker(BaseChecker):
    def get_bookable_movies(self, branches: List[str] = None, days_ahead: int = 0) -> List[MovieInfo]:
        if branches:
            return self._fetch_by_branches(branches, days_ahead)
        return self._fetch_all(days_ahead)

    # ── 지점 지정 없음: 전국 스케줄 기반 (날짜/시간 포함) ───────────
    def _fetch_all(self, days_ahead: int = 0) -> List[MovieInfo]:
        headers = {
            **self.HEADERS,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.megabox.co.kr/booking/timetable",
        }
        dates = [
            (datetime.now() + timedelta(days=d)).strftime("%Y%m%d")
            for d in range(days_ahead + 1)
        ]
        all_schedules = []
        for date_str in dates:
            try:
                resp = requests.post(
                    MEGABOX_SCHEDULE_URL,
                    data=json.dumps({"masterType": "brch", "playDe": date_str}),
                    headers=headers,
                    timeout=15,
                )
                resp.raise_for_status()
                items = resp.json().get("megaMap", {}).get("movieFormList", [])
                for item in items:
                    item["_play_date"] = date_str
                all_schedules.extend(items)
            except Exception as e:
                print(f"[메가박스] 전국 스케줄 조회 실패 ({date_str}): {e}")

        movies: List[MovieInfo] = []
        seen = set()
        for item in all_schedules:
            if item.get("bokdAbleAt") != "Y":
                continue
            title = (item.get("rpstMovieNm") or item.get("movieNm", "")).strip()
            if not title:
                continue
            brch_nm = item.get("brchNm", "")
            play_date = item.get("_play_date", "")
            play_start_time = item.get("playStartTime", "")
            event_label = (item.get("eventDivCdNm") or "").strip()
            event_progrs = (item.get("eventProgrs") or "").strip()
            if event_label and event_progrs:
                event_label = f"{event_label}({event_progrs})"
            key = (title, brch_nm, event_label, play_date, play_start_time)
            if key in seen:
                continue
            seen.add(key)
            movie_no = item.get("movieNo", "")
            brch_no = item.get("brchNo", "")
            if brch_no and play_date and movie_no:
                booking_url = (
                    f"https://www.megabox.co.kr/booking/timetable"
                    f"?brchNo={brch_no}&playDe={play_date}&movieNo={movie_no}"
                )
            else:
                booking_url = "https://www.megabox.co.kr/booking"
            date_display = f"{play_date[:4]}-{play_date[4:6]}-{play_date[6:]}" if play_date else ""
            extra = (f"📅 {date_display}" if date_display else "") + (f" {play_start_time}" if play_start_time else "")
            movies.append(
                MovieInfo(
                    title=title,
                    theater="메가박스",
                    booking_url=booking_url,
                    branch=brch_nm,
                    extra=extra,
                    event_label=event_label,
                    play_date=play_date,
                )
            )

        return movies

    # ── 지점 지정: N일치 스케줄 기반 ───────────────────────────────
    def _fetch_by_branches(self, branch_keywords: List[str], days_ahead: int = 0) -> List[MovieInfo]:
        headers = {
            **self.HEADERS,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.megabox.co.kr/booking/timetable",
        }

        # 오늘부터 days_ahead 일 후까지 날짜 목록 생성
        dates = [
            (datetime.now() + timedelta(days=d)).strftime("%Y%m%d")
            for d in range(days_ahead + 1)
        ]

        all_schedules = []
        for date_str in dates:
            try:
                resp = requests.post(
                    MEGABOX_SCHEDULE_URL,
                    data=json.dumps({"masterType": "brch", "playDe": date_str}),
                    headers=headers,
                    timeout=10,
                )
                resp.raise_for_status()
                items = resp.json().get("megaMap", {}).get("movieFormList", [])
                # 날짜 정보를 각 item에 주입
                for item in items:
                    item["_play_date"] = date_str
                all_schedules.extend(items)
            except Exception as e:
                print(f"[메가박스] 지점별 스케줄 조회 실패 ({date_str}): {e}")

        movies: List[MovieInfo] = []
        seen = set()

        for item in all_schedules:
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
            event_label = (item.get("eventDivCdNm") or "").strip()
            event_progrs = (item.get("eventProgrs") or "").strip()
            if event_label and event_progrs:
                event_label = f"{event_label}({event_progrs})"

            play_date = item.get("_play_date", "")
            play_start_time = item.get("playStartTime", "")
            # 날짜+시간까지 dedup key에 포함 — 같은 영화라도 회차별로 알림
            key = (title, brch_nm, event_label, play_date, play_start_time)
            if key in seen:
                continue
            seen.add(key)

            movie_no = item.get("movieNo", "")
            brch_no = item.get("brchNo", "")
            # 직접 예매 페이지 URL
            if brch_no and play_date and movie_no:
                booking_url = (
                    f"https://www.megabox.co.kr/booking/timetable"
                    f"?brchNo={brch_no}&playDe={play_date}&movieNo={movie_no}"
                )
            else:
                booking_url = "https://www.megabox.co.kr/booking"
            # 날짜 포맷 변환 (20260410 → 2026-04-10)
            date_display = f"{play_date[:4]}-{play_date[4:6]}-{play_date[6:]}" if play_date else ""
            extra = (f"📅 {date_display}" if date_display else "") + (f" {play_start_time}" if play_start_time else "")
            movies.append(
                MovieInfo(
                    title=title,
                    theater="메가박스",
                    booking_url=booking_url,
                    branch=brch_nm,
                    extra=extra,
                    event_label=event_label,
                    play_date=play_date,
                )
            )

        return movies
