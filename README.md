# Discord Chat Bot

개인 Discord 서버에서 사용하는 Groq AI 챗봇이자 음악 재생 봇입니다.

## 명령어

- `/chat`: 현재 채널에서 사용자별 AI 대화 시작
- `/end`: 현재 사용자의 AI 대화 종료 및 기록 초기화
- `/help`: 등록된 명령어 표시
- `/music_play query:<검색어 또는 URL>`: 음성 채널에서 음악 재생 또는 큐 추가
- `/music_pause`, `/music_resume`: 음악 일시정지·재개
- `/music_skip`: 현재 곡 건너뛰기
- `/music_queue`: 현재 곡과 대기열 표시
- `/music_stop`: 재생 중단 및 대기열 초기화
- `/music_leave`: 재생 중단 후 음성 채널 퇴장

## 구조

```text
src/
├─ bot/         # Discord 앱 생성과 명령어 동기화
├─ cogs/        # Discord 명령어와 이벤트
├─ services/    # AI 세션 및 음악 재생 유스케이스
├─ integrations/ # Groq·yt-dlp 등 외부 API 어댑터
├─ ai/          # Groq 대화 처리
├─ config/      # 환경변수 설정
└─ utils/       # 로깅과 메시지 유틸리티
```

Discord Cog는 입력과 응답만 담당하고, 실제 기능 흐름은 `services`에서 처리합니다.

## 환경변수

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
DISCORD_TOKEN=your_discord_bot_token

GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=qwen/qwen3.6-27b
# AI_SYSTEM_PROMPT=optional_custom_prompt

```

`.env`는 Git에 커밋하지 않습니다.

## 로컬 실행

Python 3.12 환경을 권장합니다.

```bash
python -m venv .venv
pip install -r requirements.txt
python main.py
```

음악 재생에는 시스템 FFmpeg가 필요합니다. Docker 이미지에는 FFmpeg가 자동으로
설치됩니다.

## Synology Container Manager

1. 저장소 파일을 NAS의 프로젝트 폴더에 복사합니다.
2. `.env`와 `secrets/gcp-service-account.json`을 준비합니다.
3. `compose.yaml`로 Container Manager 프로젝트를 생성합니다.

`main.py`와 `src`는 컨테이너에 읽기 전용으로 마운트됩니다. Python 코드만 수정한
경우에는 이미지 재빌드 없이 컨테이너를 재시작하면 적용됩니다. `requirements.txt`
또는 `Dockerfile`이 변경된 경우에는 이미지를 다시 빌드해야 합니다. 음악 기능을
처음 배포할 때는 FFmpeg와 Discord 음성 패키지 설치를 위해 반드시 재빌드합니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

## License

Copyright (c) 2024 Gloryciel

All rights reserved. This project is proprietary and confidential. Unauthorized copying, distribution, or use without explicit permission from the author is prohibited.
