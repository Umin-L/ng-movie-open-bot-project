from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class MovieInfo:
    title: str
    theater: str          # CGV / 롯데시네마 / 메가박스
    booking_url: str
    branch: str = ""      # 지점명 (예: 코엑스, 강남)
    extra: str = ""       # 추가 정보 (상영 타입 등)
    event_label: str = "" # 이벤트 라벨 (예: 무대인사, GV, 시사회)
    play_date: str = ""   # 상영 날짜 (YYYYMMDD)

    def __eq__(self, other):
        return (
            self.title == other.title
            and self.theater == other.theater
            and self.branch == other.branch
            and self.event_label == other.event_label
        )

    def __hash__(self):
        return hash((self.title, self.theater, self.branch, self.event_label))


class BaseChecker(ABC):
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    @abstractmethod
    def get_bookable_movies(
        self,
        branches: List[str] = None,
        days_ahead: int = 0,
    ) -> List[MovieInfo]:
        """
        현재 예매 가능한 영화 목록을 반환한다.
        branches   : 지점 키워드 목록 (없으면 전국)
        days_ahead : 오늘 포함 며칠 앞까지 조회할지 (0 = 오늘만)
        """
        ...

    def filter_by_keywords(self, movies: List[MovieInfo], keywords: List[str]) -> List[MovieInfo]:
        """영화 제목 키워드(부분 일치)로 필터링한다. 키워드가 비어있으면 전체 반환."""
        if not keywords:
            return movies
        result = []
        for movie in movies:
            for kw in keywords:
                if kw.lower() in movie.title.lower():
                    result.append(movie)
                    break
        return result

    def match_branch(self, branch_name: str, keywords: List[str]) -> bool:
        """지점명이 키워드 중 하나와 부분 일치하면 True."""
        if not keywords:
            return True
        return any(kw.lower() in branch_name.lower() for kw in keywords)
