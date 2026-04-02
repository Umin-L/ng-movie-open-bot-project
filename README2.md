# 텔레그램 봇 생성 가이드

MovieAlert에서 사용할 텔레그램 봇을 직접 만드는 방법입니다.

---

## 1. 봇 생성 (BotFather)

1. 텔레그램 앱에서 **@BotFather** 검색 후 대화 시작
2. `/newbot` 입력
3. 봇 이름 입력 (예: `내영화알림봇`) — 표시 이름, 자유롭게 설정
4. 사용자명 입력 (예: `my_movie_alert_bot`) — **반드시 `bot`으로 끝나야 함**
5. 완료되면 아래와 같은 토큰이 발급됩니다:

```
1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
```

이 값을 `config.json`의 `bot_token`에 붙여넣으세요.

---

## 2. Chat ID 확인

봇에게 알림을 보내려면 본인의 Chat ID가 필요합니다.

1. 방금 만든 봇을 텔레그램에서 열고 **아무 메시지나 전송** (예: `안녕`)
2. 브라우저에서 아래 URL 접속 (`<토큰>` 부분을 실제 토큰으로 교체):

```
https://api.telegram.org/bot<토큰>/getUpdates
```

3. 응답 JSON에서 아래 위치의 숫자가 Chat ID입니다:

```json
{
  "result": [
    {
      "message": {
        "chat": {
          "id": 123456789    ← 이 숫자
        }
      }
    }
  ]
}
```

이 값을 `config.json`의 `chat_id`에 붙여넣으세요.

---

## 3. config.json 적용

```json
{
  "telegram": {
    "bot_token": "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ",
    "chat_id": "123456789"
  }
}
```

---

## 4. 연결 테스트

```bash
.venv/bin/python main.py --test
```

텔레그램으로 아래 메시지가 오면 정상입니다:

```
✅ MovieAlert 연결 테스트 성공!
```

---

## 주의사항

- 봇을 만든 뒤 **반드시 봇에게 먼저 메시지를 보내야** Chat ID 조회가 됩니다.
- Chat ID는 음수(`-123456789`)일 수 있으며, 그룹 채팅방에 봇을 초대한 경우입니다. 그대로 사용하면 됩니다.
- Token은 외부에 노출되지 않도록 주의하세요.
