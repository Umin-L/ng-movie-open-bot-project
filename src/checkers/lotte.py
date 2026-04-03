"""
롯데시네마 예매 가능 영화 체커

지점 미지정: GetMoviesToBe (전국) → BookingYN='Y' 필터 (날짜/시간 없음)
지점 지정:  GetCinemaItems로 지점 ID 조회
           → GetPlaySequence로 날짜별 상영 스케줄 파싱 (날짜/시간 포함)
"""

import json
from datetime import datetime, timedelta
from typing import List

import requests

from .base import BaseChecker, MovieInfo

LOTTE_MOVIE_API    = "https://www.lottecinema.co.kr/LCWS/Movie/MovieData.aspx"
LOTTE_CINEMA_API   = "https://www.lottecinema.co.kr/LCWS/Cinema/CinemaData.aspx"
LOTTE_TICKET_API   = "https://www.lottecinema.co.kr/LCWS/Ticketing/TicketingData.aspx"
LOTTE_BOOKING_BASE = "https://www.lottecinema.co.kr/NLCJHS/Ticketing"

# AccompanyTypeCode → 이벤트 라벨
_ACCOMPANY_LABEL = {
    30:  "무대인사",
    40:  "GV",
    50:  "시사회",
    60:  "시사회",
    230: "스페셜상영회",
    260: "싱어롱",
}

_BASE_PARAM = {
    "channelType": "HO",
    "osType": "Windows NT",
    "osVersion": "Chrome",
    "multiLanguageID": "KR",
    "division": 1,
    "moviePlayYN": "Y",
    "orderType": "1",
    "blockSize": 1000,
    "pageNo": 1,
    "memberOnNo": "",
    "imgdivcd": 2,
}


class LotteChecker(BaseChecker):
    def __init__(self):
        self._headers = {
            **self.HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.lottecinema.co.kr/NLCJHS/Ticketing",
        }

    def get_bookable_movies(self, branches: List[str] = None, days_ahead: int = 0) -> List[MovieInfo]:
        if branches:
            return self._fetch_by_branches(branches, days_ahead)
        return self._fetch_all()

    # ── 지점 지정 없음: 전국 예매 가능 목록 (날짜/시간 없음) ──────────
    def _fetch_all(self) -> List[MovieInfo]:
        movies: List[MovieInfo] = []
        for play_yn, label in [("Y", "현재상영"), ("N", "개봉예정")]:
            items = self._call_movie_api(play_yn=play_yn)
            for item in items:
                m = self._to_movie_info_simple(item, label)
                if m:
                    movies.append(m)
        return movies

    # ── 지점 지정: GetPlaySequence 기반 스케줄 조회 (날짜/시간 포함) ──
    def _fetch_by_branches(self, branch_keywords: List[str], days_ahead: int = 0) -> List[MovieInfo]:
        cinemas = self._get_cinema_list()
        matched = [c for c in cinemas if self.match_branch(c["name"], branch_keywords)]
        if not matched:
            print(f"[롯데시네마] 일치하는 지점 없음: {branch_keywords}")
            return []

        dates = [
            (datetime.now() + timedelta(days=d)).strftime("%Y-%m-%d")
            for d in range(days_ahead + 1)
        ]

        movies: List[MovieInfo] = []
        seen = set()

        for cinema in matched:
            for date_str in dates:
                items = self._call_play_sequence(cinema["full_id"], date_str)
                for item in items:
                    if item.get("IsBookingYN") != "Y":
                        continue

                    title = item.get("MovieNameKR", "").strip()
                    if not title:
                        continue

                    play_dt     = item.get("PlayDt", "")       # "2026-04-08"
                    start_time  = item.get("StartTime", "")    # "09:50"
                    accompany   = item.get("AccompanyTypeCode", 10)
                    event_label = _ACCOMPANY_LABEL.get(accompany, "")

                    play_date_key = play_dt.replace("-", "") if play_dt else ""

                    key = (title, cinema["name"], event_label, play_date_key, start_time)
                    if key in seen:
                        continue
                    seen.add(key)

                    movie_code  = item.get("RepresentationMovieCode", "")
                    cinema_id   = item.get("CinemaID", "")
                    play_seq    = item.get("PlaySequence", "")
                    booking_url = (
                        f"{LOTTE_BOOKING_BASE}?cinemaID={cinema['full_id']}"
                        f"&playDate={date_str}&movieCode={movie_code}"
                        f"&playSequence={play_seq}"
                        if movie_code else LOTTE_BOOKING_BASE
                    )

                    date_display = play_dt if play_dt else ""
                    extra = (f"📅 {date_display}" if date_display else "") + \
                            (f" {start_time}" if start_time else "")

                    movies.append(MovieInfo(
                        title=title,
                        theater="롯데시네마",
                        booking_url=booking_url,
                        branch=cinema["name"],
                        extra=extra,
                        event_label=event_label,
                        play_date=play_date_key,
                    ))

        return movies

    # ── 내부 헬퍼 ─────────────────────────────────────────────────
    def _call_movie_api(self, play_yn: str, cinema_id: str = "") -> list:
        param = {**_BASE_PARAM, "MethodName": "GetMoviesToBe", "moviePlayYN": play_yn}
        if cinema_id:
            param["cinemaID"] = cinema_id
        try:
            resp = requests.post(
                LOTTE_MOVIE_API,
                data={"ParamList": json.dumps(param)},
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("IsOK") != "true":
                print(f"[롯데시네마] API 오류: {data.get('ResultMessage')}")
                return []
            return data.get("Movies", {}).get("Items", [])
        except Exception as e:
            print(f"[롯데시네마] 요청 실패: {e}")
            return []

    def _call_play_sequence(self, full_cinema_id: str, play_date: str) -> list:
        param = {
            "MethodName": "GetPlaySequence",
            "channelType": "HO",
            "osType": "W",
            "osVersion": "Mozilla/5.0",
            "playDate": play_date,
            "cinemaID": full_cinema_id,
            "representationMovieCode": "",
        }
        try:
            resp = requests.post(
                LOTTE_TICKET_API,
                data={"ParamList": json.dumps(param)},
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("IsOK") != "true":
                return []
            return data.get("PlaySeqs", {}).get("Items", [])
        except Exception as e:
            print(f"[롯데시네마] 스케줄 조회 실패 ({full_cinema_id} {play_date}): {e}")
            return []

    def _get_cinema_list(self) -> List[dict]:
        param = {
            "MethodName": "GetCinemaItems",
            "channelType": "HO",
            "osType": "Windows NT",
            "osVersion": "Chrome",
            "multiLanguageID": "KR",
        }
        try:
            resp = requests.post(
                LOTTE_CINEMA_API,
                data={"ParamList": json.dumps(param)},
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("Cinemas", {}).get("Items", [])
            return [
                {
                    "id":      str(c["CinemaID"]),
                    "full_id": f"{c['DivisionCode']}|1|{c['CinemaID']}",
                    "name":    c["CinemaNameKR"],
                }
                for c in items
            ]
        except Exception as e:
            print(f"[롯데시네마] 지점 목록 조회 실패: {e}")
            return []

    def _to_movie_info_simple(self, item: dict, label: str) -> "MovieInfo | None":
        title = item.get("MovieNameKR", "").strip()
        if not title or item.get("BookingYN") != "Y":
            return None
        movie_code  = item.get("RepresentationMovieCode", "")
        booking_url = (
            f"{LOTTE_BOOKING_BASE}?movieCd={movie_code}&movieName={title}"
            if movie_code else LOTTE_BOOKING_BASE
        )
        event_label = ""
        if item.get("StageGreetingYN") == "Y":
            event_label = "무대인사"
        elif item.get("GalaYN") == "Y" or item.get("GVyn") == "Y":
            event_label = "GV"
        elif item.get("PreviewYN") == "Y" or item.get("SpecialScreeningYN") == "Y":
            event_label = "시사회"

        return MovieInfo(
            title=title,
            theater="롯데시네마",
            booking_url=booking_url,
            branch="",
            extra=f"예매가능 | {label}",
            event_label=event_label,
        )
