# 보험 영업 모닝브리프

매일 아침 보험 뉴스를 모아 보여주는 GitHub Pages 사이트입니다.
기본 구성은 **생명보험·GA 뉴스 최대 5건 / 한국시간 오전 8시**입니다.

## 들어 있는 기능

- 한 장 요약: 뉴스 5건을 페이지 넘김 없이 한 문서에 모두 표시, A4 인쇄용 간격 적용
- 신문형: 전체 기사 모아 읽기
- 기사별 매체·발행일·원문 링크
- 날짜별 보관함, 날짜·제목 검색, 날짜가 포함된 공유 링크
- 수집처 공개: 설정된 매체, 최근 수집 성공 매체, 현재 발행본에 선정된 매체 구분
- 브라우저 인쇄 또는 PDF 저장
- 공개 RSS 수집, 최근 5일 이내 기사 우선순위 선정, URL·유사 제목 중복 제거
- 수집 실패 시 기존 뉴스 보존. 새 기사 선정이 없으면 발행일을 바꾸지 않고 수집 확인 시각만 갱신

## 처음 게시하기 — GitHub 웹사이트만 사용

1. GitHub에서 새 저장소를 만듭니다. 이름은 `insurance-morning`, 공개 범위는 **Public**, **Add README**를 선택합니다. 기본 브랜치는 `main`으로 둡니다.
2. 이 프로젝트의 파일과 폴더를 저장소 최상위에 올립니다. `insurance-morning` 폴더 자체가 한 겹 더 들어가지 않도록 주의합니다. `.github/workflows/daily.yml`도 꼭 포함해야 합니다. macOS에서는 `Command + Shift + .`로 숨김 파일을 볼 수 있습니다. GitHub의 **Add file → Upload files**에서 `.github` 폴더까지 올려주세요. 숨김 폴더 업로드가 어렵다면 **Add file → Create new file**에서 `.github/workflows/daily.yml`을 입력하고 해당 파일 내용을 붙여넣어 생성할 수 있습니다.
3. 저장소의 **Settings → Pages → Build and deployment → Source → GitHub Actions**를 선택합니다.
4. **Actions → Daily insurance briefing → Run workflow**를 한 번 실행합니다. 실행 허용 안내가 나오면 저장소의 워크플로를 활성화합니다.
5. 빌드와 배포가 초록색으로 완료되면 **Settings → Pages** 또는 배포 작업의 `github-pages` 링크에서 실제 주소를 확인합니다.

이후 매일 한국시간 오전 8시에 자동 실행을 예약합니다. GitHub Actions의 예약 실행은 혼잡할 때 지연될 수 있어 정각 갱신을 보장하지 않습니다. 정시성이 꼭 필요하다면 외부 스케줄러로 `workflow_dispatch`를 호출하는 별도 구성이 필요합니다.

공개 저장소의 예약 작업은 저장소 활동이 60일간 없으면 비활성화될 수 있습니다. 이 프로젝트는 매번 `data/status.json`을 갱신해 커밋합니다. Actions 실패 알림을 켜고 간헐적으로 실행 상태를 확인해주세요. 브랜치 보호 규칙이 봇의 직접 커밋을 막는 경우, 기록 저장 단계의 권한·보호 규칙에 맞춰 운영 방식을 조정해야 합니다.

## 어떤 기사인가요?

기본 수집 대상은 보험저널·한국보험신문·보험신보·서울파이낸스·연합뉴스·뉴시스·매일경제 7개 매체의 공개 RSS입니다. 매체마다 RSS에 노출되는 기사 범위와 개수가 달라 인터넷 전체 기사를 전수 수집하는 것은 아닙니다. 뉴스 5건은 관련 키워드 점수와 발행 시각으로 자동 선정하므로 사람이 판단한 ‘중요도 상위 5건’과 다를 수 있습니다. 매체·기사 분류를 다양하게 담되 관련 기사 수가 부족하면 기사 분류 제한만 완화합니다. 관련성 기준을 충족하는 경제·종합매체 기사가 있으면 최소 1건을 함께 담습니다. 매체당 최대 2건 제한은 유지하며, 적격 기사가 부족하면 5건 미만을 표시합니다. 경제지의 일반 기사나 비보험 신상품이 들어오지 않도록 보험 관련 문맥도 검사합니다. 기사가 5건 미만이면 확인된 기사만 게시합니다.

기본 모드는 **RSS 핵심 문장 요약**입니다. 기사별로 서론(배경), 본론(주요 사실·수치), 결론(마무리·전망)을 나누어 표시합니다. 광고·구독 안내는 제거하고 RSS의 완결된 문장에서 근거를 추립니다. RSS가 짧으면 선정된 기사에 한해 해당 매체의 공개 본문 중 일부를 추가로 확인합니다. 로그인·구독이 필요한 기사는 추가 수집하지 않습니다. 제공된 내용이 부족하면 부족함을 표시합니다. 최신 기사 부족, RSS 장애, AI 대체 표시를 화면에서 구분합니다. 서로 다른 날짜에 계속 중요한 기사가 다시 선정될 수 있습니다. 같은 날짜에 다시 실행하면 해당 날짜 발행본을 갱신합니다.

## 설정 바꾸기

`config.json`을 편집해 저장하면 다시 빌드합니다.

| 설정 | 역할 |
|---|---|
| `title` | 사이트 이름 |
| `subtitle` | 소개 문구 |
| `edition_label` | 상단 주제 표시 |
| `daily_count` | 최대 기사 수, 1~10 |
| `max_age_hours` | 발행 후 수집 허용 시간, 기본 120시간 |
| `keywords` | 기사 제목에 들어 있으면 가산하는 단어와 점수 |
| `exclude_keywords` | 기사 제목에 들어 있으면 제외하는 단어 |
| `context_keywords` | 기사 제목에서 보험 관련 문맥을 확인하는 단어 |
| `max_per_source` | 한 매체에서 선정할 수 있는 최대 건수, 기본 2 |
| `feeds` | 출처 이름과 RSS 주소 |
| `ai.enabled` | AI 해설 사용 여부, 기본 `false` |

KB손해보험·전속 중심으로 바꾸려면 `keywords`에 `KB손해보험`, `전속`, `지점장`, `LC`, `손해보험`, `설계사`, `육성` 등을 추가하고 점수를 높이세요. 특정 관점의 정확한 7:3 비중을 보장하는 기능은 현재 포함하지 않았습니다.

시간을 바꾸려면 `.github/workflows/daily.yml`의 `cron`을 수정합니다. 현재 `0 23 * * *`는 UTC 23:00, 한국시간 다음 날 08:00입니다.

## 선택: AI 서론·본론·결론 요약

AI를 쓰지 않아도 자동 수집과 사이트는 작동합니다. AI를 사용하려면:

1. 저장소 **Settings → Secrets and variables → Actions → New repository secret**에 이름 `OPENAI_API_KEY`로 API 키를 직접 등록합니다. 코드나 공개 파일, 채팅에 키를 붙여넣지 마세요.
2. `config.json`의 `ai.enabled`를 `true`로 바꿉니다.
3. 기본 모델은 `gpt-4.1-mini`입니다. 다른 모델은 `ai.model` 또는 저장소 Actions 변수 `OPENAI_MODEL`로 지정합니다.

OpenAI API 사용료는 별도입니다. ChatGPT 구독과 별개이므로 API 계정의 과금 설정과 사용 한도를 확인하세요. 이 프로젝트는 새 선정 기사 묶음당 요청 1회, 최대 출력 2,400토큰으로 제한합니다. **AI는 수집한 제목과 기사 발췌를 근거로 요약합니다.** AI 요약도 서론·본론·결론 세 문장 형식을 사용하며, 입력에 없는 전망·상품 조건을 만들지 않도록 지시합니다. AI가 실패하면 RSS 발췌로 계속 게시합니다. 이 환경에서는 API 키 없이 기본 수집 모드를 검증했으며, 유료 AI 호출은 실행하지 않았습니다.

## 로컬 실행

외부 Python 패키지 설치 없이 Python 3.11 이상을 사용합니다.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/update_news.py
python3 scripts/build.py
python3 -m http.server 8000 --directory dist
```

브라우저에서 `http://localhost:8000`을 엽니다. 배포 대상은 `dist`뿐입니다. `.env`, 워크플로, 스크립트는 게시하지 않습니다.

## 파일 안내

```text
config.json                    주제·출처·AI 설정
web/                           화면 HTML·CSS·JavaScript
scripts/update_news.py         뉴스 수집·선정·저장
scripts/build.py               공개 사이트 만들기
data/latest.json               최신 발행본
data/editions/YYYY-MM-DD.json   날짜별 발행본
data/archive.json              보관함 목록
data/status.json               마지막 수집 확인 상태
.github/workflows/daily.yml     오전 8시 수집·저장·배포
tests/test_collector.py         날짜·중복·RSS 등 검증
```

이 사이트는 특정 보험사의 공식 서비스가 아닙니다. 각 기사와 콘텐츠의 권리는 원 출처에 있습니다. 공개 RSS 주소와 제공 범위가 바뀌면 `feeds`를 조정해야 합니다.

## 참고 문서

- [GitHub Pages 사용자 정의 워크플로](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub Actions 예약 실행](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [보험저널 RSS 안내](https://www.insjournal.co.kr/rssIndex.html)
- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
