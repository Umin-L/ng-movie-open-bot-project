# MovieAlert — Oracle VM + Jenkins 배포 가이드

> **사전 지식 없이도 따라할 수 있습니다.**
> 각 단계를 순서대로 진행하세요.

---

## 전체 흐름

```
① Oracle Cloud 가입 → ② VM 생성 → ③ SSH 접속
→ ④ 자동 세팅 스크립트 실행 → ⑤ Jenkins 접속 및 파이프라인 생성
→ ⑥ 완료 (1분마다 자동 체크)
```

---

## 1단계 — Oracle Cloud 가입

1. [cloud.oracle.com](https://cloud.oracle.com) 접속
2. **Start for free** 클릭
3. 이름, 이메일, 국가(South Korea) 입력
4. 신용카드 등록 (**실제 결제 없음** — 본인 확인용)
5. 가입 완료 후 로그인

> ⚠️ 가입 심사에 최대 1~2일 걸릴 수 있습니다.

---

## 2단계 — VM 인스턴스 생성

1. Oracle Cloud 콘솔 접속 후 상단 검색창에 **"Instances"** 검색 → 클릭
2. **Create instance** 클릭
3. 아래와 같이 설정:

   | 항목 | 값 |
   |---|---|
   | Name | `movie-alert` |
   | Image | **Ubuntu 22.04** |
   | Shape | **VM.Standard.A1.Flex** (ARM, 무료) |
   | OCPU | `2` |
   | Memory | `12 GB` |
   | Network | 기본값 |

4. **SSH 키 설정**:
   - "Generate a key pair for me" 선택
   - **Private Key 다운로드** (`.key` 파일) → 잘 보관!

5. **Create** 클릭 → 생성까지 2~3분 대기

6. 생성 완료 후 **Public IP 주소** 메모 (예: `140.xxx.xxx.xxx`)

---

## 3단계 — Oracle 보안 규칙 설정 (포트 열기)

Jenkins 웹 화면에 접근하려면 **8080 포트**를 열어야 합니다.

1. 인스턴스 상세 페이지 → **Subnet** 링크 클릭
2. **Security List** 클릭
3. **Add Ingress Rules** 클릭
4. 아래 규칙 추가:

   | 항목 | 값 |
   |---|---|
   | Source CIDR | `0.0.0.0/0` |
   | IP Protocol | TCP |
   | Destination Port | `8080` |

5. **Add Ingress Rules** 저장

---

## 4단계 — SSH 접속

### Mac / Linux

```bash
# 다운로드한 키 파일 권한 설정
chmod 400 ~/Downloads/your-key.key

# SSH 접속 (IP는 본인 VM IP로 변경)
ssh -i ~/Downloads/your-key.key ubuntu@140.xxx.xxx.xxx
```

### Windows

1. [PuTTY 다운로드](https://www.putty.org/)
2. PuTTYgen으로 `.key` → `.ppk` 변환
3. PuTTY 접속: Host = `ubuntu@140.xxx.xxx.xxx`, Auth에 `.ppk` 파일 선택

---

## 5단계 — 자동 세팅 스크립트 실행

SSH 접속 후 아래 명령어를 **순서대로** 실행하세요.

```bash
# 1. 프로젝트 클론
git clone https://github.com/YOUR_ID/YOUR_REPO.git /tmp/moviealert-setup
cd /tmp/moviealert-setup

# 2. 스크립트 실행 권한 부여
chmod +x scripts/setup_oracle.sh

# 3. 자동 세팅 실행 (중간에 몇 가지 입력 요청됨)
./scripts/setup_oracle.sh
```

스크립트 실행 중 아래 항목을 입력하라고 요청합니다:

| 입력 요청 | 예시 |
|---|---|
| GitHub 레포 URL | `https://github.com/yourname/movie-alert.git` |
| SUPABASE_URL | `https://xxxx.supabase.co` |
| SUPABASE_SERVICE_KEY | Supabase → Settings → API → service_role |
| TELEGRAM_BOT_TOKEN | BotFather에서 받은 토큰 |

> 스크립트가 완료되면 Jenkins URL과 초기 비밀번호가 화면에 출력됩니다.

---

## 6단계 — Jenkins 초기 설정

1. 브라우저에서 `http://VM_IP:8080` 접속
2. "Unlock Jenkins" 화면에 스크립트 마지막에 출력된 **초기 비밀번호** 입력
3. **Install suggested plugins** 클릭 (자동 설치, 2~3분 소요)
4. 관리자 계정 생성 (아이디/비밀번호 설정)
5. Jenkins URL 확인 → **Save and Finish** → **Start using Jenkins**

---

## 7단계 — Jenkins 파이프라인 생성

1. Jenkins 메인 화면 → **New Item** 클릭
2. 이름: `MovieAlert` 입력
3. **Pipeline** 선택 → **OK**
4. 설정 화면에서:

   **Build Triggers 섹션:**
   - ✅ **Build periodically** 체크
   - Schedule: `* * * * *` 입력 (1분마다)

   **Pipeline 섹션:**
   - Definition: **Pipeline script from SCM** 선택
   - SCM: **Git** 선택
   - Repository URL: `https://github.com/YOUR_ID/YOUR_REPO.git`
   - Branch: `*/main`
   - Script Path: `Jenkinsfile`

5. **Save** 클릭

---

## 8단계 — 첫 실행 확인

1. `MovieAlert` 파이프라인 → **Build Now** 클릭
2. 빌드 번호 클릭 → **Console Output** 클릭
3. 아래와 같은 로그가 나오면 성공:

```
[2026-04-03 12:00:00] MovieAlert 워커 시작
[워커] 활성 사용자 2명

  [사용자 abc12345...]
    [MegaboxChecker] 3개 매칭
    [LotteChecker] 2개 매칭
    → 현재 예매가능: 5개
    → 신규 감지: 5개

[워커] 완료 (45.2초)
```

---

## ✅ 완료!

이제 Jenkins가 **1분마다 자동으로 영화 예매 오픈을 체크**합니다.

- 새 예매 오픈 감지 → 텔레그램 알림 즉시 발송
- 코드 변경 시 GitHub push → 다음 실행 때 자동 반영

---

## 자주 묻는 질문

### Q. VM이 꺼지면?
Oracle Cloud는 Always Free VM을 임의로 종료하지 않습니다. 단, 직접 Stop 누르면 Jenkins도 멈춥니다.

### Q. VM이 재시작됐는데 Jenkins가 안 켜져요
```bash
sudo systemctl start jenkins
```

### Q. Jenkins 비밀번호를 잊어버렸어요
```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

### Q. 코드를 수정했는데 반영이 안 돼요
Jenkins 파이프라인에 `git pull` 단계가 있어서 다음 1분 실행 때 자동 반영됩니다.
즉시 반영하려면 Jenkins에서 **Build Now** 클릭.

### Q. 로그는 어디서 봐요?
Jenkins → MovieAlert → 빌드 번호 → **Console Output**

---

## 기존 GitHub Actions와 비교

| | GitHub Actions (이전) | Jenkins + Oracle (현재) |
|---|---|---|
| 체크 주기 | 5분 (지연 있음) | **1분 (정확)** |
| 실행 환경 | 매번 새 컨테이너 | 상시 실행 VM |
| 비용 | 무료 | **무료** |
| 관리 | 없음 | SSH로 VM 관리 |
