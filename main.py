#!/usr/bin/env python3
"""
MovieAlert — 영화관 예매 오픈 감지 & 텔레그램 알림

사용법:
    python main.py              # config.json 설정으로 N분마다 반복 실행
    python main.py --once       # 1회만 체크하고 종료 (크론탭 용도)
    python main.py --test       # 텔레그램 연결 테스트 후 종료
    python main.py --check      # 알림 없이 현재 예매 가능 영화 목록만 출력
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import List

import schedule

from src.checkers.base import MovieInfo
from src.checkers.cgv import CGVChecker
from src.checkers.lotte import LotteChecker
from src.checkers.megabox import MegaboxChecker
from src.notifier import TelegramNotifier
from src.state import detect_new

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        print(f"[오류] config.json 파일이 없습니다: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_movies(config: dict) -> List[MovieInfo]:
    keywords: List[str] = config.get("movies", [])
    branches: List[str] = config.get("branches", [])
    event_labels: List[str] = config.get("event_labels", [])
    theater_flags: dict = config.get("theaters", {})

    checkers = []
    if theater_flags.get("cgv", True):
        checkers.append(CGVChecker())
    if theater_flags.get("lotte", True):
        checkers.append(LotteChecker())
    if theater_flags.get("megabox", True):
        checkers.append(MegaboxChecker())

    all_movies: List[MovieInfo] = []
    for checker in checkers:
        name = checker.__class__.__name__
        try:
            movies = checker.get_bookable_movies(branches=branches if branches else None)
            filtered = checker.filter_by_keywords(movies, keywords)

            # 이벤트 라벨 필터:
            # - event_labels 가 비어있으면 이벤트 없는 영화만 포함
            # - event_labels 가 있으면 이벤트 없는 영화 + 일치하는 이벤트 영화 포함
            if event_labels:
                filtered = [
                    m for m in filtered
                    if not m.event_label
                    or any(el.lower() in m.event_label.lower() for el in event_labels)
                ]
            else:
                filtered = [m for m in filtered if not m.event_label]

            all_movies.extend(filtered)

            branch_info = f" / 지점: {', '.join(branches)}" if branches else ""
            print(f"[{name}] 전체 {len(movies)}개 중 {len(filtered)}개 매칭{branch_info}")
        except Exception as e:
            print(f"[오류] {name} 실행 중 예외: {e}")

    return all_movies


def run_check(config: dict, notifier: TelegramNotifier) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{now}] 체크 시작")

    all_movies = collect_movies(config)
    new_movies = detect_new(all_movies)

    if new_movies:
        print(f"[알림] 새 예매 가능 {len(new_movies)}개 → 텔레그램 전송")
        for m in new_movies:
            branch_str = f" ({m.branch})" if m.branch else ""
            event_str = f" [{m.event_label}]" if m.event_label else ""
            print(f"       [{m.theater}{branch_str}]{event_str} {m.title}")
        notifier.send_movie_alert(new_movies)
    else:
        print("[체크] 새로운 변경 없음")


def main():
    parser = argparse.ArgumentParser(description="MovieAlert 영화 예매 오픈 알리미")
    parser.add_argument("--test", action="store_true", help="텔레그램 연결 테스트")
    parser.add_argument("--once", action="store_true", help="1회 체크 후 종료")
    parser.add_argument("--check", action="store_true", help="현재 예매 가능 영화 목록만 출력 (알림 없음)")
    args = parser.parse_args()

    config = load_config()

    if args.check:
        movies = collect_movies(config)
        branches = config.get("branches", [])
        branch_info = f" (지점: {', '.join(branches)})" if branches else ""
        print(f"\n현재 예매 가능 영화{branch_info} — 총 {len(movies)}개:")
        for m in movies:
            branch_str = f" [{m.branch}]" if m.branch else ""
            event_str = f" [이벤트: {m.event_label}]" if m.event_label else ""
            print(f"  [{m.theater}]{branch_str}{event_str} {m.title} | {m.extra}")
        return

    tg = config.get("telegram", {})
    bot_token = tg.get("bot_token", "")
    chat_id = tg.get("chat_id", "")

    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("[오류] config.json의 telegram.bot_token을 설정해주세요.")
        sys.exit(1)
    if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        print("[오류] config.json의 telegram.chat_id를 설정해주세요.")
        sys.exit(1)

    notifier = TelegramNotifier(bot_token, chat_id)

    if args.test:
        ok = notifier.test_connection()
        if ok:
            notifier.send_text("✅ MovieAlert 연결 테스트 성공!")
        sys.exit(0 if ok else 1)

    interval = config.get("check_interval_minutes", 5)
    movie_targets = config.get("movies", ["전체"])
    branch_targets = config.get("branches", ["전체"])
    event_targets = config.get("event_labels", [])
    print(f"[시작] MovieAlert 실행 중 — {interval}분마다 체크")
    print(f"       감시 영화: {movie_targets}")
    print(f"       감시 지점: {branch_targets}")
    if event_targets:
        print(f"       감시 이벤트: {event_targets}")

    if args.once:
        run_check(config, notifier)
        return

    run_check(config, notifier)
    schedule.every(interval).minutes.do(run_check, config=config, notifier=notifier)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
