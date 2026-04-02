# MovieAlert 🎬

CGV · 롯데시네마 · 메가박스의 예매 오픈을 자동으로 감지하고, 텔레그램 봇으로 알림을 보내는 프로젝트입니다.

---

## 동작 방식

1. N분마다 3개 영화관의 예매 가능 영화 목록을 수집합니다.
2. 이전 상태와 비교하여 **새로 예매 가능해진 영화**를 감지합니다.
3. 감지된 영화가 있으면 텔레그램 봇으로 즉시 알림을 전송합니다.

---

## 시작하기

### 1. 의존성 설치

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium     # CGV 크롤링용 (필수)
```

### 2. 텔레그램 봇 준비

텔레그램 봇이 없다면 아래 순서로 만듭니다.

1. 텔레그램에서 **@BotFather** 검색
2. `/newbot` 명령 입력 → 봇 이름 설정
3. 발급된 **Bot Token** 복사
4. 봇에게 메시지를 먼저 한 번 보낸 뒤, 아래 URL로 Chat ID 확인:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   응답의 `result[0].message.chat.id` 값이 Chat ID입니다.

### 3. config.json 설정

```json
{
  "telegram": {
    "bot_token": "1234567890:ABCdef...",
    "chat_id": "123456789"
  },
  "check_interval_minutes": 5,
  "movies": [
    "명탐정 코난",
    "어벤져스"
  ],
  "branches": [
    "코엑스",
    "강남"
  ],
  "event_labels": [
    "무대인사",
    "GV",
    "시사회"
  ],
  "theaters": {
    "cgv": true,
    "lotte": true,
    "megabox": true
  }
}
```

| 항목 | 설명 |
|------|------|
| `bot_token` | BotFather에서 발급받은 토큰 |
| `chat_id` | 알림받을 채팅 ID |
| `check_interval_minutes` | 체크 주기 (분 단위, 기본값 5) |
| `movies` | 감시할 영화 제목 키워드 목록 (비워두면 전체 감시) |
| `branches` | 감시할 지점 이름 키워드 목록 (비워두면 전국 감시) |
| `event_labels` | 감시할 이벤트 라벨 목록 (무대인사 / GV / 시사회 등, 비워두면 이벤트 감시 안 함) |
| `theaters` | 각 영화관 활성화 여부 (`true` / `false`) |

> **movies, branches 모두 비워두면** 전국 모든 지점의 모든 영화를 감시합니다.
> 제목/지점명은 일부만 입력해도 부분 일치로 동작합니다 (예: `"코엑스"`, `"강남"`).

### event_labels 동작 방식

| `event_labels` 설정 | 동작 |
|---|---|
| `[]` (비워둠) | 이벤트 없는 일반 상영만 감시 |
| `["무대인사"]` | 일반 상영 + 무대인사 상영 감시 |
| `["무대인사", "GV", "시사회"]` | 일반 상영 + 3가지 이벤트 모두 감시 |

이벤트 라벨이 감지되면 텔레그램 알림에 `🎤 무대인사` 형태로 표시됩니다.

> **지원 범위**: 메가박스는 지점(`branches`) 설정 시 이벤트 라벨을 정확히 감지합니다.
> CGV·롯데시네마는 API 구조에 따라 감지 여부가 다를 수 있습니다.

### 지점명 입력 주의사항

지점명은 각 영화관이 실제로 사용하는 이름을 기준으로 합니다.

| 영화관 | 지점명 예시 |
|--------|------------|
| CGV | `강남`, `홍대`, `용산아이파크몰`, `왕십리` |
| 롯데시네마 | `월드타워`, `건대입구`, `홍대입구`, `노원` |
| 메가박스 | `코엑스`, `강남`, `홍대`, `수원스타필드` |

> 영화관마다 같은 지역도 지점명이 다를 수 있습니다. 정확한 지점명이 불확실할 경우 지역명 일부(예: `"홍대"`, `"강남"`)만 입력하면 해당 키워드를 포함하는 모든 지점을 감시합니다.

---

## 실행 방법

### 텔레그램 연결 테스트

```bash
.venv/bin/python main.py --test
```

봇 연결이 정상이면 텔레그램으로 테스트 메시지가 전송됩니다.

### 현재 예매 가능 영화 목록 확인

```bash
.venv/bin/python main.py --check
```

알림 없이 현재 예매 가능한 영화 목록만 터미널에 출력합니다.

### 1회만 실행 (크론탭 연동용)

```bash
.venv/bin/python main.py --once
```

### 반복 실행 (메인 모드)

```bash
.venv/bin/python main.py
```

`check_interval_minutes` 주기로 계속 실행됩니다. 첫 실행 시에는 상태를 저장만 하고 알림을 보내지 않으며, 이후 새로 예매 가능해진 영화가 생기면 텔레그램으로 알림을 전송합니다.

---

## 백그라운드 실행 (선택)

터미널을 닫아도 계속 실행하려면 `nohup` 또는 `screen`을 사용합니다.

```bash
# nohup
nohup .venv/bin/python main.py > movie_alert.log 2>&1 &

# 로그 확인
tail -f movie_alert.log

# 프로세스 종료
kill $(pgrep -f "main.py")
```

---

## 프로젝트 구조

```
MovieAlert_PJT/
├── main.py                 # 실행 진입점
├── config.json             # 설정 파일 (토큰, 영화 목록, 주기)
├── state.json              # 자동 생성 — 이전 예매 상태 저장
├── requirements.txt        # Python 패키지 목록
└── src/
    ├── checkers/
    │   ├── base.py         # 기본 클래스 (MovieInfo, BaseChecker)
    │   ├── cgv.py          # CGV 체커 (Playwright 헤드리스 브라우저)
    │   ├── lotte.py        # 롯데시네마 체커 (JSON API)
    │   └── megabox.py      # 메가박스 체커 (JSON API)
    ├── notifier.py         # 텔레그램 메시지 전송
    └── state.py            # 상태 비교 및 저장
```

---

## 각 영화관 구현 방식

| 영화관 | 방식 | 예매 가능 판단 기준 |
|--------|------|-------------------|
| CGV | Playwright 헤드리스 브라우저 | "예매하기" 버튼 존재 여부 |
| 롯데시네마 | HTTP JSON API | `BookingYN == "Y"` |
| 메가박스 | HTTP JSON API | `bokdAbleYn == "Y"` |

> CGV는 API 인증이 필요하여 헤드리스 브라우저로 실제 페이지를 렌더링하는 방식을 사용합니다.

---

## 알림 예시

```
🎬 영화 예매 오픈 알림!

CGV — 명탐정 코난: 세기말의 마술사
  예매가능
  예매하기

메가박스 (코엑스) — 명탐정 코난: 세기말의 마술사
  예매가능 | 상영예정 | 개봉: 2026.04.18
  예매하기

메가박스 (코엑스) — 명탐정 코난: 세기말의 마술사 🎤 무대인사
  예매가능 | 개봉예정
  예매하기
```
