# 4-Day Solar Wind Forecasting

2011–2023년 public 자료로 모델을 개발하고, 2024–2025년 private 자료에서 4일 뒤 태양풍 속도를 예측하는 그룹 미니 컴피티션입니다.

자세한 내용은 [COMPETITION.md](COMPETITION.md) 및 [COMPETITION.html](COMPETITION.html)를 참고하세요.

---

## 데이터

| 위치 | 내용 |
|------|------|
| 이 저장소 | CSV 데이터, 코드, 문서 |
| [HuggingFace Dataset](https://huggingface.co/datasets/<username>/solar-wind-aia193) | SDO/AIA 193Å FITS (6.1 GB), 시각화 PNG (5.1 GB) |

### CSV 파일

| 파일 | 기간 | 용도 |
|------|------|------|
| `solar_wind-public.csv` | 2011–2023 | 모델 개발용 |
| `solar_wind-private.csv` | 2024–2025 | 최종 holdout 평가용 |
| `solar_wind_data.csv` | 2011–2025 | 전체 결합 데이터 |

### 변수

| 열 | 단위 |
|----|------|
| `datetime` | UTC, 1시간 간격 |
| `Speed (km/s)` | 태양풍 속도 (예측 대상) |
| `Density (1/cm^3)` | 양성자 수밀도 |
| `Temperature (K)` | 양성자 온도 |
| `B (nT)` | 행성간 자기장 크기 |
| `Sunspot Number` | 일별 흑점 수 |
| `Coronal Hole Area` | 중앙자오선 띠 CH 면적 비율 (일별) |

---

## 시작하기

```bash
git clone https://github.com/<username>/solar-wind
cd solar-wind
uv sync
```

FITS/PNG가 필요한 경우 HuggingFace에서 추가로 다운로드합니다.

```bash
huggingface-cli download <username>/solar-wind-aia193 --repo-type dataset --local-dir .
```

---

## 데이터 생성 파이프라인

이미 생성된 CSV가 저장소에 포함되어 있으므로 아래 과정은 재현 시에만 필요합니다.

```bash
uv run omni.py                       # OMNI2 TXT → sw_data.csv
uv run extract_ch_area.py            # AIA FITS → ch_area_output.csv
uv run prepare_competition_data.py   # 결합 및 public/private 분할
uv run omni_plot.py                  # 전체 기간 시각화
```

---

## 예측 문제

```
Target = Speed(t + 4 days)
```

각 시점 `t`에서 그 시점까지 관측된 정보만 사용해 4일 뒤 속도를 예측합니다.

---

## Baseline 결과 (Private: 2024–2025, N=17,280)

| Baseline | MAE (km/s) | RMSE (km/s) | CC | MAE Skill |
|----------|------------|-------------|----|-----------|
| Public mean (417.20) | **77.82** | **108.85** | — | 0.025 |
| 27-day persistence | 79.85 | 111.39 | **0.427** | 0.000 |
| Public median (397.00) | 80.48 | 115.69 | — | -0.008 |
| 4-day persistence | 104.72 | 137.60 | 0.146 | -0.312 |

---

## 제출 형식

```csv
datetime,predicted_speed
2024-01-01 00:30:00,401.2
2024-01-01 01:30:00,398.7
```

`submissions/` 폴더에 CSV를 저장한 뒤 `evaluate_submissions.py`의 `SUBMISSION_FILES`에 경로를 추가하고 실행합니다.

```bash
uv run make_baseline_submissions.py   # baseline 4종 생성
uv run evaluate_submissions.py        # 랭킹 출력 및 저장
```
