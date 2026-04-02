"""
이전 상태와 현재 상태를 비교하여 새로 예매 가능해진 영화를 감지합니다.
상태는 state.json 파일에 영속적으로 저장됩니다.
(title, theater, branch, event_label) 조합으로 구분합니다.
"""

import json
import os
from typing import List, Set, Tuple

from .checkers.base import MovieInfo

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "state.json")


def _load() -> Set[Tuple[str, str, str, str]]:
    """저장된 상태를 (title, theater, branch, event_label) 튜플 집합으로 로드한다."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            (item["title"], item["theater"], item.get("branch", ""), item.get("event_label", ""))
            for item in data
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save(movies: List[MovieInfo]) -> None:
    """현재 예매 가능 목록을 상태 파일에 저장한다."""
    data = [
        {"title": m.title, "theater": m.theater, "branch": m.branch, "event_label": m.event_label}
        for m in movies
    ]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def detect_new(current: List[MovieInfo]) -> List[MovieInfo]:
    """
    이전 상태와 비교하여 새로 추가된 영화만 반환한다.
    상태 파일이 없으면 첫 실행으로 간주하여 현재 목록 전체를 저장하고
    빈 리스트를 반환한다 (첫 실행 시 알림 폭탄 방지).
    """
    previous = _load()
    is_first_run = len(previous) == 0

    current_keys = {(m.title, m.theater, m.branch, m.event_label) for m in current}
    new_keys = current_keys - previous

    _save(current)

    if is_first_run:
        print(f"[상태] 첫 실행 — 현재 상태 {len(current)}개 저장, 알림 없음")
        return []

    new_movies = [m for m in current if (m.title, m.theater, m.branch, m.event_label) in new_keys]
    if new_movies:
        print(f"[상태] 새 예매 감지 {len(new_movies)}개!")
    return new_movies
