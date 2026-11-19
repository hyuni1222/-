# 보험 영업 모닝브리프

생명보험·GA 뉴스를 수집해 GitHub Pages에 발행합니다. GitHub Actions는 매일 오전 8시(한국 시간)에 예약되어 있으며 실제 실행 시각은 지연될 수 있습니다.

## 뉴스와 날씨 업데이트

```bash
python3 -m unittest discover -s tests -v
python3 scripts/update_weather.py
python3 scripts/update_news.py
python3 scripts/build.py
```

날씨는 Open-Meteo의 서울 좌표(37.5665, 126.9780) 현재 기상 모델과 당일 최저·최고 예보를 사용합니다. 브라우저에서도 접속 시와 30분마다 갱신합니다. API 호출 실패 시 오늘 날짜의 저장본만 표시하며, 지난 날짜의 예보는 오늘 날씨로 표시하지 않습니다. 별도 API 키가 필요하지 않습니다.

## 지난 날짜 수집

```bash
python3 scripts/backfill_news.py --start 2026-11-11 --end 2026-11-19
python3 scripts/build.py
```

보험저널·한국보험신문·보험신보·서울파이낸스의 공개 목록에서 해당 날짜에 발행된 기사를 확인합니다. 하루 최대 5건, 매체별 최대 2건을 선정하며, 관련 기사를 확인하지 못한 날짜는 0건으로 남깁니다. 현재 발행본은 유지합니다.

`data/backfill-report.json`에 날짜별 수집처·후보 수·선정 수·오류를 기록합니다. 소급 수집은 과거 예약 실행 성공 기록과 다르며 화면에도 별도로 표시됩니다. 예약 실행은 저장소의 Actions 실행 내역에서 확인할 수 있습니다.
