# MovieAlert 배포 가이드

전체 흐름: **Supabase** (DB·인증) + **GitHub** (워커) + **Vercel** (웹)

---

## 1단계 — Supabase 설정

### 1-1. 프로젝트 생성
1. [supabase.com](https://supabase.com) → **New project**
2. 프로젝트 이름: `movie-alert` / 비밀번호 메모

### 1-2. DB 스키마 적용
1. Supabase 대시보드 → **SQL Editor**
2. `supabase/schema.sql` 전체 내용 붙여넣기 → **Run**

### 1-3. 초대 코드 생성 (최초 1회)
SQL Editor에서 실행:
```sql
INSERT INTO invite_codes (code) VALUES
  ('MOVIE-AAAA'),
  ('MOVIE-BBBB'),
  ('MOVIE-CCCC');
-- 사용자 수만큼 추가
```

### 1-4. 키 복사
**Settings → API** 에서:
- `Project URL` → `SUPABASE_URL`
- `anon public` key → `SUPABASE_ANON_KEY`
- `service_role` key → `SUPABASE_SERVICE_KEY` (절대 외부 노출 금지)

---

## 2단계 — 텔레그램 봇 생성

1. 텔레그램에서 **@BotFather** 검색
2. `/newbot` → 봇 이름·사용자명 입력
3. 발급된 **토큰** 메모 → `TELEGRAM_BOT_TOKEN`
4. 봇 사용자명 메모 → `TELEGRAM_BOT_USERNAME` (예: `MovieAlertBot`)

---

## 3단계 — GitHub 레포 설정

### 3-1. 레포 생성 및 코드 업로드
```bash
cd /Users/umin/Desktop/MovieAlert_PJT
git init
git add .
git commit -m "init"
# GitHub에서 새 레포 생성 후:
git remote add origin https://github.com/YOUR_ID/movie-alert.git
git push -u origin main
```

> ⚠️ 레포는 **Public** 으로 설정해야 GitHub Actions 무제한 무료 실행 가능

### 3-2. GitHub Secrets 등록
레포 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름 | 값 |
|---|---|
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service_role key |
| `TELEGRAM_BOT_TOKEN` | BotFather 발급 토큰 |

### 3-3. Actions 활성화 확인
레포 → **Actions** 탭 → 워크플로우가 보이면 OK

> 첫 실행은 수동으로: Actions → **MovieAlert Worker** → **Run workflow**

---

## 4단계 — Vercel 배포 (웹 대시보드)

### 4-1. Vercel 가입 및 프로젝트 연결
1. [vercel.com](https://vercel.com) → GitHub 계정으로 로그인
2. **New Project** → 위에서 만든 `movie-alert` 레포 선택
3. **Root Directory**: `web` 으로 변경
4. Framework Preset: **Vite** 자동 감지됨

### 4-2. 환경변수 입력
Vercel 배포 설정 화면에서:

| 변수명 | 값 |
|---|---|
| `VITE_SUPABASE_URL` | Supabase Project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key |
| `VITE_TELEGRAM_BOT_USERNAME` | 봇 사용자명 (@ 없이) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 (API Route용) |

### 4-3. Deploy 클릭
배포 완료 후 URL 확인 (예: `https://movie-alert-xxx.vercel.app`)

---

## 5단계 — 사용자 초대

1. 배포된 URL을 사용자에게 공유
2. SQL에서 생성한 초대 코드를 개별 전달
3. 사용자가 URL 접속 → 회원가입 (초대 코드 + 이메일 + 비밀번호)
4. 설정 페이지에서 텔레그램 연결

---

## 사용자 흐름

```
1. URL 접속 → 초대 코드로 회원가입
2. 설정 → 봇에게 /start 전송 → Chat ID 자동 조회 → 저장
3. 설정 → 감시할 영화명 / 지점 / 이벤트 라벨 입력 → 저장
4. GitHub Actions가 5분마다 체크 → 새 예매 오픈 시 텔레그램 알림
5. 대시보드에서 감지 이력 확인
```

---

## 로컬 개발

```bash
cd web
cp .env.example .env       # 환경변수 채우기
npm install
npm run dev                # http://localhost:5173
```

---

## 구조 요약

```
MovieAlert_PJT/
├── .github/workflows/
│   └── movie-alert.yml       # 5분마다 실행되는 GitHub Actions
├── worker/
│   └── main_worker.py        # 멀티유저 체크 워커
├── src/checkers/             # 기존 CGV·롯데·메가박스 체커
├── supabase/
│   └── schema.sql            # DB 초기화 스크립트
├── web/                      # Vite + React 프론트엔드
│   ├── api/telegram/
│   │   └── get-chat-id.js    # Vercel Serverless (chat_id 자동 조회)
│   ├── src/
│   │   ├── pages/Auth.jsx
│   │   ├── pages/Dashboard.jsx
│   │   └── pages/Settings.jsx
│   └── vercel.json
└── requirements.txt
```

---

## 추가 초대 코드 발급

```sql
-- Supabase SQL Editor에서 실행
INSERT INTO invite_codes (code) VALUES ('MOVIE-DDDD');
```

## 사용자 비활성화

```sql
UPDATE user_profiles SET is_active = false WHERE id = 'USER_UUID';
```
