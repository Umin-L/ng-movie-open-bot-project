"""
MovieAlert 멀티유저 워커
Jenkins(Oracle VM)에서 1분마다 실행됨

환경변수 로딩 순서:
  1. 프로젝트 루트의 .env 파일 (Oracle VM 로컬 실행)
  2. 시스템 환경변수 (GitHub Actions 등 CI 환경)

필수 환경변수:
  SUPABASE_URL          - Supabase 프로젝트 URL
  SUPABASE_SERVICE_KEY  - Supabase Service Role Key (RLS 우회)
  TELEGRAM_BOT_TOKEN    - 공유 텔레그램 봇 토큰
"""

import os
import sys
import json
import requests
import traceback
from datetime import datetime, timezone
from pathlib import Path

# ── 프로젝트 루트를 sys.path에 추가 ─────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.checkers.lotte import LotteChecker
from src.checkers.megabox import MegaboxChecker
from src.checkers.base import MovieInfo


# ── .env 파일 로딩 (존재하는 경우에만) ──────────────────────
def _load_dotenv():
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:   # 이미 있으면 덮어쓰지 않음
                os.environ[key] = val

_load_dotenv()


# ── 환경변수 검증 ────────────────────────────────────────────
def _require_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise EnvironmentError(
            f"환경변수 '{name}'가 없습니다.\n"
            f"  - Oracle VM: /opt/moviealert/.env 파일에 추가\n"
            f"  - GitHub Actions: Secrets에 추가"
        )
    return val

SUPABASE_URL         = _require_env("SUPABASE_URL").rstrip("/")
SUPABASE_SERVICE_KEY = _require_env("SUPABASE_SERVICE_KEY")
TELEGRAM_BOT_TOKEN   = _require_env("TELEGRAM_BOT_TOKEN")

_HEADERS = {
    "apikey":        SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}


# ── Supabase REST 헬퍼 ──────────────────────────────────────
def sb_get(table: str, params: dict = None) -> list:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=_HEADERS, params=params, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def sb_post(table: str, payload: list) -> list:
    if not payload:
        return []
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=_HEADERS, json=payload, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def sb_delete(table: str, params: dict) -> None:
    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=_HEADERS, params=params, timeout=15,
    )
    resp.raise_for_status()


# ── 텔레그램 단일 메시지 발송 ────────────────────────────────
def _send_telegram_message(chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id":                  chat_id,
            "text":                     text,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": True,
        }, timeout=10)
        result = resp.json()
        if not result.get("ok"):
            print(f"  [텔레그램] 전송 실패: {result.get('description')}")
            return False
        return True
    except Exception as e:
        print(f"  [텔레그램] 오류: {e}")
        return False


# ── 텔레그램 알림 (날짜별 + 청크 분리, 중복 압축) ───────────
def send_telegram(chat_id: str, movies: list) -> bool:
    from collections import defaultdict

    THEATER_ICON = {"롯데시네마": "🔴", "메가박스": "🟣"}
    TG_MAX = 3800  # 텔레그램 4096자 제한에 여유

    # play_date 기준으로 그룹핑
    groups = defaultdict(list)
    for m in movies:
        groups[m.play_date].append(m)

    success = True
    for date_key in sorted(groups.keys()):
        group = groups[date_key]
        if date_key:
            date_display = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}"
            header = f"🎬 *영화 예매 오픈 알림! ({date_display})*"
        else:
            header = "🎬 *영화 예매 오픈 알림!*"

        # (title, theater, event_label) 기준으로 중복 압축, 지점 목록 수집
        seen: dict = {}  # key → {"theater": str, "branches": set, "event_label": str}
        for m in group:
            key = (m.title, m.theater, m.event_label)
            if key not in seen:
                seen[key] = {"theater": m.theater, "branches": set(), "event_label": m.event_label}
            if m.branch:
                seen[key]["branches"].add(m.branch)

        # 알림 라인 생성
        movie_lines = []
        for (title, _, event_label), info in seen.items():
            icon       = THEATER_ICON.get(info["theater"], "🎬")
            branches   = sorted(info["branches"])
            if branches:
                branch_str = f" ({', '.join(branches)})"
            else:
                branch_str = ""
            event_str  = f" 🎤 *{event_label}*" if event_label else ""
            movie_lines.append(f"{icon} *{info['theater']}{branch_str}* — {title}{event_str}")

        # 메시지가 너무 길면 청크로 분할
        chunks = []
        current = []
        for line in movie_lines:
            # 헤더 + 현재 누적 + 새 줄 길이 체크
            body = "\n".join(current + [line])
            if current and len(header) + 2 + len(body) > TG_MAX:
                chunks.append(list(current))
                current = [line]
            else:
                current.append(line)
        if current:
            chunks.append(current)

        for i, chunk in enumerate(chunks):
            suffix = f" ({i+1}/{len(chunks)})" if len(chunks) > 1 else ""
            text = header + suffix + "\n\n" + "\n".join(chunk)
            if not _send_telegram_message(chat_id, text):
                success = False

    return success


# ── 사용자별 영화 체크 ──────────────────────────────────────
def check_for_user(cfg: dict) -> list:
    keywords   = cfg.get("movies", [])
    branches   = cfg.get("branches", []) or None
    ev_labels  = cfg.get("event_labels", [])
    days_ahead = int(cfg.get("check_days_ahead", 0))

    checkers = []
    if cfg.get("lotte_enabled", True):
        checkers.append(LotteChecker())
    if cfg.get("megabox_enabled", True):
        checkers.append(MegaboxChecker())

    all_movies = []
    for checker in checkers:
        name = checker.__class__.__name__
        try:
            kw_arg = {"keywords": keywords} if isinstance(checker, LotteChecker) else {}
            movies   = checker.get_bookable_movies(branches=branches, days_ahead=days_ahead, **kw_arg)
            print(f"    [{name}] 전체 조회: {len(movies)}개")
            filtered = checker.filter_by_keywords(movies, keywords)
            print(f"    [{name}] 키워드 필터 후: {len(filtered)}개")
            if filtered:
                labels = list({m.event_label for m in filtered})
                print(f"    [{name}] 감지된 라벨: {labels}")

            # 이벤트 필터 (ev_labels 설정 시에만 필터링, 미설정 시 전체 통과)
            CGV_ONLY_LABELS = {"시네마톡"}
            if ev_labels:
                filtered = [
                    m for m in filtered
                    if m.event_label
                    and any(el.lower() in m.event_label.lower() for el in ev_labels)
                    and not (
                        any(lbl in m.event_label for lbl in CGV_ONLY_LABELS)
                        and m.theater != "CGV"
                    )
                ]

            all_movies.extend(filtered)
            print(f"    [{name}] 라벨 필터 후: {len(filtered)}개 최종 매칭")
        except Exception as e:
            print(f"    [{name}] 오류: {e}")
            traceback.print_exc()

    return all_movies


# ── 상태 비교 및 신규 감지 ──────────────────────────────────
def detect_new(user_id: str, current: list) -> list:
    # KST 자정 기준으로 오늘 저장된 상태만 "이미 감지됨"으로 처리
    # → 날짜가 바뀌면 동일 영화도 다시 신규 감지 → 알림 재발송
    from datetime import timedelta
    KST = timezone(timedelta(hours=9))
    today_start_kst = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_kst.astimezone(timezone.utc)
    filter_dt = today_start_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    rows = sb_get("movie_states", {
        "user_id":     f"eq.{user_id}",
        "detected_at": f"gte.{filter_dt}",
        "select":      "title,theater,branch,event_label,play_date",
    })
    prev_keys = {
        (r["title"], r["theater"], r["branch"], r["event_label"], r.get("play_date", ""))
        for r in rows
    }

    return [
        m for m in current
        if (m.title, m.theater, m.branch, m.event_label, m.play_date) not in prev_keys
    ]


def sync_state(user_id: str, current: list) -> None:
    """현재 목록으로 DB 상태를 전체 교체한다."""
    sb_delete("movie_states", {"user_id": f"eq.{user_id}"})
    if current:
        seen: set = set()
        deduped: list = []
        for m in current:
            key = (m.title, m.theater, m.branch, m.event_label, m.play_date)
            if key not in seen:
                seen.add(key)
                deduped.append(m)
        sb_post("movie_states", [
            {
                "user_id":     user_id,
                "title":       m.title,
                "theater":     m.theater,
                "branch":      m.branch,
                "event_label": m.event_label,
                "play_date":   m.play_date,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }
            for m in deduped
        ])


def save_detections(user_id: str, movies: list) -> None:
    """신규 감지 영화를 이력 테이블에 저장한다. (title+theater+event_label 기준 중복 제거)"""
    if not movies:
        return
    seen: set = set()
    deduped = []
    for m in movies:
        key = (m.title, m.theater, m.event_label)
        if key not in seen:
            seen.add(key)
            deduped.append(m)
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
        for m in deduped
    ])


# ── 메인 ────────────────────────────────────────────────────
def main():
    start_time = datetime.now()
    print(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] MovieAlert 워커 시작")

    # 활성 사용자 조회 (telegram_chat_id 설정된 사용자만)
    try:
        profiles = sb_get("user_profiles", {
            "is_active":        "eq.true",
            "telegram_chat_id": "neq.",
            "select":           "id,telegram_chat_id,last_checked_at",
        })
    except Exception as e:
        print(f"[워커] Supabase 연결 실패: {e}")
        sys.exit(1)

    print(f"[워커] 활성 사용자 {len(profiles)}명")
    if not profiles:
        print("[워커] 처리할 사용자 없음. 종료.")
        return

    now_utc = datetime.now(timezone.utc)

    # 사용자별 처리
    for profile in profiles:
        user_id = profile["id"]
        chat_id = profile["telegram_chat_id"]
        print(f"\n  [사용자 {user_id[:8]}...]")

        try:
            # 설정 조회
            cfg_rows = sb_get("user_configs", {
                "user_id": f"eq.{user_id}",
                "select":  "movies,branches,event_labels,cgv_enabled,lotte_enabled,megabox_enabled,check_days_ahead,check_interval_minutes",
            })
            cfg = cfg_rows[0] if cfg_rows else {}

            # 인터벌 체크 — 설정한 주기가 지나지 않았으면 스킵
            interval_min = int(cfg.get("check_interval_minutes") or 5)
            last_checked = profile.get("last_checked_at")
            if last_checked:
                last_dt     = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
                elapsed_min = (now_utc - last_dt).total_seconds() / 60
                if elapsed_min < interval_min:
                    print(f"    → 스킵 (인터벌 {interval_min}분, 경과 {elapsed_min:.1f}분)")
                    continue

            # last_checked_at 업데이트
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/user_profiles",
                headers=_HEADERS,
                params={"id": f"eq.{user_id}"},
                json={"last_checked_at": now_utc.isoformat()},
                timeout=10,
            )

            # 영화 체크
            current_movies = check_for_user(cfg)
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

        except Exception as e:
            print(f"  [오류] 사용자 {user_id[:8]} 처리 중 예외: {e}")
            traceback.print_exc()
            continue

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n[워커] 완료 ({elapsed:.1f}초)")


if __name__ == "__main__":
    main()
