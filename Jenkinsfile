// ============================================================
//  MovieAlert Jenkins 파이프라인
//
//  - 1분마다 자동 실행 (cron 트리거)
//  - GitHub에서 최신 코드 자동 반영 (git pull)
//  - 실패 시 텔레그램으로 에러 알림
// ============================================================

pipeline {
    agent any

    // 1분마다 실행
    triggers {
        cron('* * * * *')
    }

    environment {
        PROJECT_DIR = '/opt/moviealert'
        PYTHON      = '/opt/moviealert/.venv/bin/python'
        // .env 파일에서 환경변수 자동 로드 (setup_oracle.sh 실행 시 생성됨)
        ENV_FILE    = '/opt/moviealert/.env'
    }

    options {
        // 이전 빌드가 아직 실행 중이면 스킵 (중복 실행 방지)
        disableConcurrentBuilds()
        // 빌드 타임아웃 5분
        timeout(time: 5, unit: 'MINUTES')
        // 오래된 빌드 로그는 최근 100개만 보관
        buildDiscarder(logRotator(numToKeepStr: '100'))
    }

    stages {

        stage('코드 최신화') {
            steps {
                dir("${PROJECT_DIR}") {
                    sh 'git pull origin main'
                }
            }
        }

        stage('영화 체크') {
            steps {
                dir("${PROJECT_DIR}") {
                    // .env 파일에서 환경변수 로드 후 워커 실행
                    sh '''#!/bin/bash
                        set -a
                        source /opt/moviealert/.env
                        set +a
                        ${PYTHON} worker/main_worker.py
                    '''
                }
            }
        }

    }

    post {
        failure {
            // 빌드 실패 시 텔레그램으로 에러 알림
            script {
                def envVars = [:]
                try {
                    readFile("${ENV_FILE}").split('\n').each { line ->
                        def parts = line.tokenize('=')
                        if (parts.size() >= 2) {
                            envVars[parts[0].trim()] = parts[1..-1].join('=').trim()
                        }
                    }
                } catch (e) { /* 파일 읽기 실패 무시 */ }

                def token = envVars['TELEGRAM_BOT_TOKEN'] ?: ''
                if (token) {
                    sh """
                        curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \\
                          -d "chat_id=${envVars['ADMIN_CHAT_ID'] ?: ''}" \\
                          -d "text=⚠️ MovieAlert 워커 오류 발생\\n빌드 #${BUILD_NUMBER}\\n확인: ${BUILD_URL}" \\
                          || true
                    """
                }
            }
        }
        success {
            // 성공은 로그만 남김 (매분 알림은 너무 많음)
            echo "✅ 체크 완료 — ${new Date().format('yyyy-MM-dd HH:mm:ss')}"
        }
    }
}
