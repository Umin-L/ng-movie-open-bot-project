#!/bin/bash
# =============================================================
#  MovieAlert — Oracle VM 자동 세팅 스크립트
#  Oracle Cloud Ubuntu 22.04 ARM VM에서 한 번만 실행하세요.
#
#  사용법:
#    chmod +x setup_oracle.sh
#    ./setup_oracle.sh
# =============================================================

set -e  # 오류 발생 시 즉시 중단

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "======================================================"
echo "   MovieAlert Oracle VM 세팅 시작"
echo "======================================================"
echo ""

# ── 1. 시스템 패키지 업데이트 ──────────────────────────────
info "시스템 패키지 업데이트 중..."
sudo apt-get update -y && sudo apt-get upgrade -y
success "시스템 업데이트 완료"

# ── 2. Java 설치 (Jenkins 필수) ────────────────────────────
info "Java 설치 중..."
sudo apt-get install -y fontconfig openjdk-17-jre
java -version
success "Java 설치 완료"

# ── 3. Jenkins 설치 ────────────────────────────────────────
info "Jenkins 설치 중..."
sudo wget -O /usr/share/keyrings/jenkins-keyring.asc \
  https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc]" \
  https://pkg.jenkins.io/debian-stable binary/ | \
  sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y jenkins
sudo systemctl enable jenkins
sudo systemctl start jenkins
success "Jenkins 설치 완료"

# ── 4. Python 3.11 설치 ────────────────────────────────────
info "Python 3.11 설치 중..."
sudo apt-get install -y python3.11 python3.11-venv python3-pip python3.11-dev
# python3 명령이 3.11을 가리키도록 설정
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
python3 --version
success "Python 3.11 설치 완료"

# ── 5. 시스템 의존성 설치 (Playwright/Chromium용) ──────────
info "브라우저 의존성 설치 중..."
sudo apt-get install -y \
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
  libgbm1 libasound2 libpango-1.0-0 libcairo2 \
  wget curl git unzip
success "브라우저 의존성 설치 완료"

# ── 6. 프로젝트 클론 ───────────────────────────────────────
info "프로젝트 클론 중..."
read -p "GitHub 레포 URL을 입력하세요 (예: https://github.com/yourname/movie-alert.git): " REPO_URL
if [ -z "$REPO_URL" ]; then
  error "레포 URL을 입력해야 합니다."
fi

PROJECT_DIR="/opt/moviealert"
sudo mkdir -p "$PROJECT_DIR"
sudo chown "$USER:$USER" "$PROJECT_DIR"
git clone "$REPO_URL" "$PROJECT_DIR"
success "프로젝트 클론 완료: $PROJECT_DIR"

# ── 7. Python 가상환경 및 패키지 설치 ─────────────────────
info "Python 가상환경 생성 및 패키지 설치 중..."
cd "$PROJECT_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
success "Python 패키지 설치 완료"

# ── 8. Playwright Chromium 설치 ────────────────────────────
info "Playwright Chromium 설치 중 (시간이 걸릴 수 있습니다)..."
.venv/bin/playwright install chromium
success "Playwright 설치 완료"

# ── 9. 환경변수 파일 생성 ──────────────────────────────────
info "환경변수 파일 생성 중..."
ENV_FILE="$PROJECT_DIR/.env"

read -p "SUPABASE_URL을 입력하세요: " SUPABASE_URL
read -p "SUPABASE_SERVICE_KEY를 입력하세요: " SUPABASE_SERVICE_KEY
read -p "TELEGRAM_BOT_TOKEN을 입력하세요: " TELEGRAM_BOT_TOKEN

cat > "$ENV_FILE" <<EOF
SUPABASE_URL=$SUPABASE_URL
SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
EOF

chmod 600 "$ENV_FILE"  # 파일 소유자만 읽기/쓰기 가능
success "환경변수 파일 생성 완료: $ENV_FILE"

# ── 10. Oracle 방화벽에서 Jenkins 포트 열기 (8080) ─────────
info "방화벽 설정 중..."
sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
# 재시작 후에도 유지되도록 저장
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
success "포트 8080 열림"

# ── 11. Jenkins가 프로젝트 디렉터리 접근할 수 있도록 권한 설정
info "Jenkins 권한 설정 중..."
sudo usermod -aG "$USER" jenkins
sudo chown -R "$USER:jenkins" "$PROJECT_DIR"
sudo chmod -R 775 "$PROJECT_DIR"
success "Jenkins 권한 설정 완료"

# ── 완료 ───────────────────────────────────────────────────
JENKINS_PASS=$(sudo cat /var/lib/jenkins/secrets/initialAdminPassword 2>/dev/null || echo "이미 설정됨")
SERVER_IP=$(curl -s ifconfig.me)

echo ""
echo "======================================================"
echo -e "${GREEN}   세팅 완료!${NC}"
echo "======================================================"
echo ""
echo -e "  Jenkins 접속 URL : ${CYAN}http://${SERVER_IP}:8080${NC}"
echo -e "  초기 비밀번호     : ${YELLOW}${JENKINS_PASS}${NC}"
echo -e "  프로젝트 경로     : ${CYAN}${PROJECT_DIR}${NC}"
echo ""
echo "  다음 단계:"
echo "  1. Oracle Cloud 콘솔 → 보안 그룹에서 8080 포트 열기"
echo "  2. 위 URL로 Jenkins 접속"
echo "  3. 초기 비밀번호 입력 후 설정 완료"
echo "  4. README_JENKINS.md 의 'Jenkins 파이프라인 설정' 따라하기"
echo ""
