"""
MovieAlert 멀티유저 워커
GitHub Actions에서 5분마다 실행됨

환경변수:
  SUPABASE_URL          - Supabase 프로젝트 URL
  SUPABASE_SERVICE_KEY  - Supabase Service Role Key (RLS 우회)
  TELEGRAM_BOT_TOKEN    - 공유 텔레그램 봇 토큰
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone

# 프로젝트 루트를 sys.path에 추가 (src.checkers 임포트용)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.checkers.cgv import CGVChecker
from src.checkers.lotte import LotteChecker
from src.checkers.megabox import MegaboxChecker
from src.checkers.base import MovieInfo

# ── 환경변수 ────────────────────────────────────────────────
SUPABASE_URL        = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


# ── Supabase REST 헬퍼 ──────────────────────────────────────
def sb_get(table: str, params: dict = None) -> list:
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                        headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def sb_post(table: str, payload) -> list:
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                         headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def sb_delete(table: str, params: dict) -> None:
    resp = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}",
                           headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()


def sb_upsert(table: str, payload, on_conflict: str) -> list:
    h = {**HEADERS, "Prefer": f"resolution=merge-duplicates,return=representation"}
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}",
        headers=h, json=payload, timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ── 텔레그램 알림 ───────────────────────────────────────────
def send_telegram(chat_id: str, movies: list[MovieInfo]) -> None:
    lines = ["🎬 *영화 예매 오픈 알림!*\n"]
    for m in movies:
        branch_str = f" ({m.branch})" if m.branch else ""
        event_str  = f" 🎤 *{m.event_label}*" if m.event_label else ""
        lines.append(f"*{m.theater}{branch_str}* — {m.title}{event_str}")
        if m.extra:
            lines.append(f"  _{m.extra}_")
        if m.booking_url:
            lines.append(f"  [예매하기]({m.booking_url})")
        lines.append("")

    text = "\n".join(lines).strip()
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=10)
        if not resp.json().get("ok"):
            print(f"  [텔레그램] 전송 실패: {resp.json().get('description')}")
    except Exception as e:
        print(f"  [텔레그램] 오류: {e}")


# ── 사용자별 영화 체크 ──────────────────────────────────────
def check_for_user(user_id: str, cfg: dict) -> list[MovieInfo]:
    """사용자 설정에 따라 영화 체커를 실행하고 예매 가능 목록을 반환한다."""
    keywords  = cfg.get("movies", [])
    branches  = cfg.get("branches", []) or None
    ev_labels = cfg.get("event_labels", [])

    checkers = []
    if cfg.get("cgv_enabled", True):
        checkers.append(CGVChecker())
    if cfg.get("lotte_enabled", True):
        checkers.append(LotteChecker())
    if cfg.get("megabox_enabled", True):
        checkers.append(MegaboxChecker())

    all_movies: list[MovieInfo] = []
    for checker in checkers:
        name = checker.__class__.__name__
        try:
            movies   = checker.get_bookable_movies(branches=branches)
            filtered = checker.filter_by_keywords(movies, keywords)

            # 이벤트 필터
            if ev_labels:
                filtered = [
                    m for m in filtered
                    if not m.event_label
                    or any(el.lower() in m.event_label.lower() for el in ev_labels)
                ]
            else:
                filtered = [m for m in filtered if not m.event_label]

            all_movies.extend(filtered)
            print(f"    [{name}] {len(filtered)}개 매칭")
        except Exception as e:
            print(f"    [{name}] 오류: {e}")

    return all_movies


# ── 상태 비교 및 신규 감지 ──────────────────────────────────
def detect_new(user_id: str, current: list[MovieInfo]) -> list[MovieInfo]:
    """DB에 저장된 이전 상태와 비교해 새로운 항목만 반환한다."""
    rows = sb_get("movie_states", {
        "user_id": f"eq.{user_id}",
        "select": "title,theater,branch,event_label",
    })
    prev_keys = {(r["title"], r["theater"], r["branch"], r["event_label"]) for r in rows}

    new_movies = []
    for m in current:
        key = (m.title, m.theater, m.branch, m.event_label)
        if key not in prev_keys:
            new_movies.append(m)

    return new_movies


def sync_state(user_id: str, current: list[MovieInfo]) -> None:
    """현재 목록으로 DB 상태를 동기화한다 (사라진 항목 삭제, 신규 추가)."""
    # 전체 교체: 기존 삭제 후 현재 목록 삽입 (upsert)
    sb_delete("movie_states", {"user_id": f"eq.{user_id}"})
    if current:
        sb_post("movie_states", [
            {
                "user_id":     user_id,
                "title":       m.title,
                "theater":     m.theater,
                "branch":      m.branch,
                "event_label": m.event_label,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }
            for m in current
        ])


def save_detections(user_id: str, movies: list[MovieInfo]) -> None:
    """신규 감지 영화를 이력 테이블에 저장한다 (대시보드 표시용)."""
    if not movies:
        return
    sb_post("detected_movies", [
        {
            "user_id":     user_id,
            "title":       m.title,
            "theater":     m.theater,
            "branch":      m.branch,
            "event_label": m.event_label,
            "booking_url": m.booking_url,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        for m in movies
    ])


# ── 메인 ────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] MovieAlert 워커 시작")

    # 1. 활성 사용자 목록 조회 (telegram_chat_id 설정된 사용자만)
    profiles = sb_get("user_profiles", {
        "is_active": "eq.true",
        "telegram_chat_id": "neq.",
        "select": "id,telegram_chat_id",
    })
    print(f"[워커] 활성 사용자 {len(profiles)}명")

    if not profiles:
        print("[워커] 처리할 사용자 없음. 종료.")
        return

    # 2. 사용자별 처리
    for profile in profiles:
        user_id  = profile["id"]
        chat_id  = profile["telegram_chat_id"]
        print(f"\n  [사용자 {user_id[:8]}...]")

        # 설정 조회
        cfg_rows = sb_get("user_configs", {
            "user_id": f"eq.{user_id}",
            "select": "movies,branches,event_labels,cgv_enabled,lotte_enabled,megabox_enabled",
        })
        cfg = cfg_rows[0] if cfg_rows else {}

        # 영화 체크
        current_movies = check_for_user(user_id, cfg)
        print(f"    → 현재 예매가능: {len(current_movies)}개")

        # 신규 감지
        new_movies = detect_new(user_id, current_movies)
        print(f"    → 신규 감지: {len(new_movies)}개")

        # 상태 동기화
        sync_state(user_id, current_movies)

        # 신규 항목이 있으면 알림 + 이력 저장
        if new_movies:
            save_detections(user_id, new_movies)
            send_telegram(chat_id, new_movies)
            for m in new_movies:
                branch_str = f" ({m.branch})" if m.branch else ""
                event_str  = f" [{m.event_label}]" if m.event_label else ""
                print(f"    ✉ [{m.theater}{branch_str}]{event_str} {m.title}")

    print(f"\n[워커] 완료")


if __name__ == "__main__":
    main()
