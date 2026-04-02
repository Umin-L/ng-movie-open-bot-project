"""
텔레그램 알림 전송 모듈
"""

import requests
from typing import List

from .checkers.base import MovieInfo


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_movie_alert(self, movies: List[MovieInfo]) -> None:
        if not movies:
            return

        lines = ["🎬 *영화 예매 오픈 알림!*\n"]
        for m in movies:
            branch_str = f" ({m.branch})" if m.branch else ""
            event_str = f" 🎤 *{m.event_label}*" if m.event_label else ""
            lines.append(f"*{m.theater}{branch_str}* — {m.title}{event_str}")
            if m.extra:
                lines.append(f"  _{m.extra}_")
            if m.booking_url:
                lines.append(f"  [예매하기]({m.booking_url})")
            lines.append("")

        self._send("\n".join(lines))

    def send_text(self, message: str) -> None:
        self._send(message)

    def _send(self, text: str) -> None:
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"[텔레그램] 메시지 전송 실패: {e}")

    def test_connection(self) -> bool:
        try:
            resp = requests.get(f"{self._base_url}/getMe", timeout=10)
            data = resp.json()
            if data.get("ok"):
                name = data["result"].get("first_name", "")
                print(f"[텔레그램] 봇 연결 성공: {name}")
                return True
            print(f"[텔레그램] 봇 연결 실패: {data.get('description')}")
            return False
        except Exception as e:
            print(f"[텔레그램] 봇 연결 오류: {e}")
            return False
