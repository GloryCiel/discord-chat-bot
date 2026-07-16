# Discord 음악 기능 구현 TODO

이 문서는 음악 기능을 한 단계씩 직접 구현하기 위한 작업 순서입니다. 각 항목의 `MUSIC-n` 번호는 소스 코드의 `TODO(MUSIC-n)` 주석과 연결됩니다.

음악 기능이 완성되기 전까지 `MusicCog`는 `DiscordBot.setup_hook()`에서 로드하지 않습니다. 따라서 중간 단계에서도 기존 AI 채팅과 Palworld 명령어는 계속 정상 작동합니다.

## 목표 명령어

```text
/music_play query:<검색어 또는 URL>
/music_pause
/music_resume
/music_skip
/music_queue
/music_stop
/music_leave
```

## 전체 흐름

```text
MusicCog
  → MusicService
    → MediaExtractor (yt-dlp)
    → Discord VoiceClient + FFmpeg
```

서버마다 별도의 `GuildMusicPlayer`를 하나씩 만들고, 플레이어마다 현재 곡·대기열·음성 연결·재생 작업을 소유합니다.

## 1. 음악 모델 이해하기 — MUSIC-1

파일: `src/domain/music.py`

- [ ] `Track`의 각 필드가 필요한 이유 확인
- [ ] `duration_label`에서 초를 `분:초` 형식으로 변환
- [ ] 라이브 방송처럼 재생 시간이 없는 경우 `LIVE` 반환
- [ ] `tests/test_music_domain.py` 테스트 통과

완료 조건:

```text
Track(..., duration_seconds=185).duration_label == "3:05"
Track(..., duration_seconds=None).duration_label == "LIVE"
```

## 2. yt-dlp로 검색 결과 가져오기 — MUSIC-2

파일: `src/integrations/media_extractor.py`

- [ ] `requirements.txt`에 `yt-dlp` 추가
- [ ] `YoutubeDL` 옵션 구성
- [ ] URL이면 해당 URL을 조회
- [ ] 검색어이면 `ytsearch1:<검색어>`로 첫 결과 조회
- [ ] 재생목록 전체가 큐에 들어오지 않도록 `noplaylist=True` 설정
- [ ] 동기식 yt-dlp 호출을 `asyncio.to_thread()`로 실행
- [ ] 결과를 `Track`으로 변환
- [ ] 직접 스트림 URL은 큐에 저장하지 않고 `get_stream_url()` 호출 시 새로 추출
- [ ] 비공개·삭제·검색 실패를 이해하기 쉬운 예외로 변환

중요: 스트림 URL은 만료될 수 있으므로 `Track`에는 원본 페이지 URL만 저장합니다.

## 3. 서버별 대기열 만들기 — MUSIC-3

파일: `src/services/music.py`

- [ ] `MusicService.get_player(guild_id)` 구현
- [ ] 서버별 플레이어가 서로 다른 큐를 갖는지 확인
- [ ] `GuildMusicPlayer.enqueue()` 구현
- [ ] 현재 곡과 대기열 목록 조회 구현
- [ ] 큐 최대 길이 결정(권장: 50곡)
- [ ] 동일 서버의 동시 명령을 보호할 `asyncio.Lock` 사용

완료 조건:

- A 서버에 추가한 곡이 B 서버 큐에 나타나지 않음
- 먼저 넣은 곡이 먼저 재생되는 FIFO 순서 유지

## 4. Discord 음성 채널 연결 — MUSIC-4

파일: `src/cogs/music.py`, `src/services/music.py`

- [ ] 명령어 사용자가 음성 채널에 있는지 검사
- [ ] 봇이 연결되지 않았으면 사용자 채널에 입장
- [ ] 다른 채널에 있다면 정책 결정: 이동하거나 오류 반환
- [ ] 봇에 `Connect`, `Speak`, `View Channel` 권한이 있는지 확인
- [ ] 서버별 `VoiceClient`를 `GuildMusicPlayer`에 연결

처음에는 “명령어 사용자가 있는 채널로 이동” 정책이 가장 단순합니다.

## 5. FFmpeg로 실제 재생 — MUSIC-5

파일: `src/services/music.py`

- [ ] `Dockerfile`에 FFmpeg 설치 추가
- [ ] `requirements.txt`의 Discord 항목을 `discord.py[voice]`로 변경
- [ ] 재생 직전에 `MediaExtractor.get_stream_url()` 호출
- [ ] `discord.FFmpegOpusAudio` 또는 `FFmpegPCMAudio` 생성
- [ ] `VoiceClient.play()` 호출
- [ ] `after` 콜백에서 이벤트 루프로 안전하게 복귀
- [ ] 한 곡 종료 후 다음 곡 자동 재생
- [ ] FFmpeg 오류를 로그에 남기고 다음 곡으로 진행

`VoiceClient.play()`의 `after` 콜백은 별도 스레드에서 실행될 수 있으므로 `loop.call_soon_threadsafe()` 또는 `asyncio.run_coroutine_threadsafe()`를 사용해야 합니다.

## 6. 슬래시 명령어 연결 — MUSIC-6

파일: `src/cogs/music.py`

- [ ] `/music_play`: 검색 후 큐 추가, 필요하면 재생 시작
- [ ] `/music_queue`: 현재 곡과 다음 곡 목록 표시
- [ ] `/music_pause`: 현재 재생 일시정지
- [ ] `/music_resume`: 일시정지 해제
- [ ] `/music_skip`: 현재 곡 중단 후 다음 곡 재생
- [ ] `/music_stop`: 현재 곡과 큐 초기화
- [ ] `/music_leave`: 재생 중단, 큐 초기화, 음성 채널 퇴장
- [ ] Discord 응답이 3초를 넘길 수 있는 명령은 먼저 `defer()` 호출

## 7. 봇에 Cog 장착 — MUSIC-7

파일: `src/bot/bot.py`

- [ ] `MediaExtractor` 생성
- [ ] `MusicService` 생성
- [ ] `MusicCog` import
- [ ] `setup_hook()`에서 `await self.add_cog(...)` 호출
- [ ] `tests/test_bot_commands.py` 예상 명령어에 음악 명령 추가
- [ ] `/help`에 음악 명령이 자동 표시되는지 확인

이 단계는 MUSIC-1부터 MUSIC-6까지 동작한 뒤 진행합니다.

## 8. 자동 퇴장과 안정성 — MUSIC-8

- [ ] 큐가 빈 상태로 5분이 지나면 자동 퇴장
- [ ] 봇만 음성 채널에 남으면 자동 퇴장할지 결정
- [ ] 곡 최대 길이 제한 검토
- [ ] 큐 길이 제한
- [ ] 중복 `/music_play` 요청 동시성 테스트
- [ ] yt-dlp 및 FFmpeg 실패 후 플레이어가 멈추지 않는지 테스트
- [ ] 봇 재연결 시 오래된 `VoiceClient` 상태 정리

## NAS 배포 체크리스트

음악 기능은 Python 패키지와 FFmpeg가 새로 필요하므로 최초 한 번은 이미지 재빌드가 필요합니다.

- [ ] `requirements.txt` 변경
- [ ] `Dockerfile`에 FFmpeg 설치
- [ ] NAS에 전체 `src` 폴더 업로드
- [ ] 이미지 재빌드
- [ ] 컨테이너 로그에서 음성 관련 오류 확인
- [ ] 음성 채널에서 재생·스킵·정지·퇴장 순서 테스트

## 작업할 때 유용한 명령

남은 TODO 검색:

```bash
rg "TODO\(MUSIC-" src
```

테스트:

```bash
python -m unittest discover -s tests -v
```
