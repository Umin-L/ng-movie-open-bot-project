"""
롯데시네마 예매 가능 영화 체커

지점 미지정: GetMoviesToBe (전국) → BookingYN='Y' 필터
지점 지정:  GetCinemaItems로 지점 ID 조회 → 각 cinemaID로 GetMoviesToBe 호출
"""

import json
from typing import List

import requests

from .base import BaseChecker, MovieInfo

LOTTE_MOVIE_API = "https://www.lottecinema.co.kr/LCWS/Movie/MovieData.aspx"
LOTTE_CINEMA_API = "https://www.lottecinema.co.kr/LCWS/Cinema/CinemaData.aspx"
LOTTE_BOOKING_BASE = "https://www.lottecinema.co.kr/NLCJHS/Ticketing"

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
            "Referer": "https://www.lottecinema.co.kr/NLCJHS/Movie/MovieList",
        }

    def get_bookable_movies(self, branches: List[str] = None) -> List[MovieInfo]:
        if branches:
            return self._fetch_by_branches(branches)
        return self._fetch_all()

    # ── 지점 지정 없음: 전국 예매 가능 목록 ──────────────────────────
    def _fetch_all(self) -> List[MovieInfo]:
        movies: List[MovieInfo] = []
        for play_yn, label in [("Y", "현재상영"), ("N", "개봉예정")]:
            items = self._call_movie_api(play_yn=play_yn)
            for item in items:
                m = self._to_movie_info(item, label, branch="")
                if m:
                    movies.append(m)
        return movies

    # ── 지점 지정: 지점별 예매 가능 목록 ──────────────────────────────
    def _fetch_by_branches(self, branch_keywords: List[str]) -> List[MovieInfo]:
        # 1. 전체 지점 목록 조회
        cinemas = self._get_cinema_list()
        # 2. 키워드 일치 지점 필터
        matched = [c for c in cinemas if self.match_branch(c["name"], branch_keywords)]
        if not matched:
            print(f"[롯데시네마] 일치하는 지점 없음: {branch_keywords}")
            return []

        movies: List[MovieInfo] = []
        seen = set()
        for cinema in matched:
            for play_yn, label in [("Y", "현재상영"), ("N", "개봉예정")]:
                items = self._call_movie_api(play_yn=play_yn, cinema_id=cinema["id"])
                for item in items:
                    m = self._to_movie_info(item, label, branch=cinema["name"])
                    if m:
                        key = (m.title, m.branch, m.event_label)
                        if key not in seen:
                            seen.add(key)
                            movies.append(m)
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
            return [{"id": str(c["CinemaID"]), "name": c["CinemaNameKR"]} for c in items]
        except Exception as e:
            print(f"[롯데시네마] 지점 목록 조회 실패: {e}")
            return []

    def _to_movie_info(self, item: dict, label: str, branch: str) -> "MovieInfo | None":
        title = item.get("MovieNameKR", "").strip()
        if not title or item.get("BookingYN") != "Y":
            return None
        movie_code = item.get("RepresentationMovieCode", "")
        rel_date = (item.get("ReleaseDate") or "")[:10]
        booking_url = (
            f"{LOTTE_BOOKING_BASE}?movieCd={movie_code}&movieName={title}"
            if movie_code
            else LOTTE_BOOKING_BASE
        )

        # 이벤트 라벨 감지 (롯데시네마 API에서 제공하는 필드 기반)
        event_label = ""
        if item.get("StageGreetingYN") == "Y":
            event_label = "무대인사"
        elif item.get("GalaYN") == "Y" or item.get("GVyn") == "Y":
            event_label = "GV"
        elif item.get("PreviewYN") == "Y" or item.get("SpecialScreeningYN") == "Y":
            event_label = "시사회"
        elif item.get("SpecialType") and item.get("SpecialType") not in ("", "0"):
            event_label = str(item["SpecialType"])

        return MovieInfo(
            title=title,
            theater="롯데시네마",
            booking_url=booking_url,
            branch=branch,
            extra=f"예매가능 | {label} | 개봉: {rel_date}",
            event_label=event_label,
        )
