# 4-Day Solar Wind Forecasting: Group Mini-Competition

## 1. 프로젝트 질문

> 2011–2023년 public 자료로 모델을 개발하고, 2024–2025년 private 자료에서 4-day 태양풍 속도 예측 성능을 평가한다.

우리는 public에서 자유롭게 분석하고 모델을 개발합니다. 개발 방법을 확정한 뒤 private에서 최종 성능을 한 번 확인합니다.

## 2. 왜 public과 private로 나누었나?

이 분할의 의도는 **과거 자료로 모델을 개발하고, 개발 과정에서 사용하지 않은 연속된 미래 기간에서 일반화 성능을 확인하는 것**입니다. 태양풍은 인접 시간의 상관이 강하므로 전체 자료를 무작위로 나누면 비슷한 시점이 train과 test에 함께 들어가 성능이 낙관적으로 보일 수 있습니다. 따라서 2011–2023은 모델과 전처리를 결정하는 development 기간으로, 그보다 미래인 2024–2025는 확정된 모델을 평가하는 holdout 기간으로 분리했습니다. 즉, 파일을 숨기기 위한 구분이 아니라 **모델 선택과 최종 평가를 분리하기 위한 실험 설계**입니다.

Kaggle competition에 비유하면 public 기간은 모델을 개발하고 public score를 확인하는 **public leaderboard 단계**, private 기간은 최종 순위를 결정하는 **private leaderboard 단계**와 비슷합니다.

### Public: 모델 개발용

`solar_wind-public.csv`

- 기간: 2011-01-01 ~ 2023-12-31
- 113,952개 시간 행
- 탐색적 분석, feature 생성, validation, 모델 학습과 hyperparameter 선택에 사용합니다.

### Private: 미래 일반화 확인용

`solar_wind-private.csv`

- 기간: 2024-01-01 ~ 2025-12-31
- 17,544개 시간 행
- Public에서 확정한 방법이 실제 미래 연속 구간에서도 작동하는지 최종 확인합니다.

여기서 private는 파일이 비밀이라는 뜻이 아니라 **development에 사용하지 않는 holdout 기간**이라는 뜻입니다. 파일을 가지고 있어도 다음 작업에는 사용하지 않습니다.

- Private 평균·중앙값·분포를 보고 feature나 모델 결정
- Private score를 보고 hyperparameter 수정
- Private 성능이 좋아질 때까지 반복 실행

Private를 본 뒤 모델을 수정하면 private는 test가 아니라 또 하나의 validation이 됩니다. Private 평가 직전에 코드와 설정을 저장하고, 평가 후에는 결과를 해석만 하는 것을 원칙으로 합니다.

### 이 연도 경계의 의미

Public은 약 13년으로 모델 개발에 충분히 길고, private는 최근 2년의 연속된 미래 구간입니다. Public에도 Solar Cycle 24와 Cycle 25 상승기 일부가 들어 있고, private는 Cycle 25의 높은 활동 수준을 포함하므로 시간 변화와 solar-cycle-related distribution shift를 함께 시험할 수 있습니다.

## 3. 데이터 생성 흐름

최종 CSV는 다음 순서로 만들어집니다.

```text
OMNI 원본 TXT
  └─ omni.py
       └─ sw_data.csv

SDO/AIA 193 Å FITS
  └─ extract_ch_area.py
       └─ ch_area_output.csv

sw_data.csv + ch_area_output.csv
  └─ prepare_competition_data.py
       ├─ solar_wind_data.csv
       ├─ solar_wind-public.csv
       └─ solar_wind-private.csv

solar_wind-public.csv + solar_wind-private.csv
  ├─ make_baseline_submissions.py → submissions/baseline_*.csv
  └─ evaluate_submissions.py → submissions/evaluation_ranking.csv
```

### `sw_data.csv`

생성 코드: `omni.py`

입력은 NASA OMNI에서 받은 `OMNI2_H0_MRG1HR_563544.txt`입니다. 코드는 주석과 헤더를 제외하고 `datetime`, Speed, Density, Temperature, B, Sunspot Number를 읽습니다. OMNI의 공식 fill value(`9999`, `999.9` 등)는 실제 관측값이 아니므로 `NaN`으로 바꿉니다.

`omni.py`는 현재 작업 폴더의 원본 TXT를 읽고 같은 폴더에 `sw_data.csv`를 저장하므로 다음처럼 실행합니다.

```bash
uv run omni.py
```

### `ch_area_output.csv`

생성 코드: `extract_ch_area.py`

JSOC의 일별 SDO/AIA 193 Å synoptic FITS를 내려받아 다음 열을 저장합니다.

- `date`: CH 영상 날짜
- `ch_area`: 중앙자오선 띠에서 CH가 차지하는 픽셀 비율
- `disk_median`: threshold 계산과 품질 확인에 사용한 태양 원반 밝기 중앙값

기본 실행만 CH CSV를 만듭니다. `--plot-only`와 `--cnn-export`는 그림 또는 CNN 입력자료만 생성합니다.

```bash
uv run extract_ch_area.py
```

### 최종 결합 및 분할 CSV

생성 코드: `prepare_competition_data.py`

이 코드는 다음 작업을 위에서 아래로 수행합니다.

1. 시간별 `sw_data.csv`와 일별 `ch_area_output.csv`를 읽습니다.
2. 같은 UTC 날짜끼리 결합합니다.
3. `ch_area`를 `Coronal Hole Area`로 바꿉니다.
4. 모델 입력에 사용하지 않는 `disk_median`은 제외합니다.
5. CH가 없는 날짜는 이전 값을 전달하지 않고 `NaN`으로 둡니다.
6. 전체 자료를 `solar_wind_data.csv`로 저장합니다.
7. 2024-01-01을 경계로 public과 private를 저장합니다.

```bash
uv run prepare_competition_data.py
```

| 생성 파일 | 기간 | 용도 |
|---|---|---|
| `solar_wind_data.csv` | 2011–2025 | 전체 결합자료 확인용 |
| `solar_wind-public.csv` | 2011–2023 | 모델 development |
| `solar_wind-private.csv` | 2024–2025 | 최종 미래 holdout 평가 |

### `omni_plot.py`: 최종 결합자료 시각화

`omni_plot.py`는 새로운 CSV를 만드는 코드가 아니라, 최종 결합된 `solar_wind_data.csv`를 읽어 전체 기간을 빠르게 확인하는 **시각화·품질검사 코드**입니다.

다음 여섯 변수를 2011–2025년 시간축에 각각 그립니다.

- Speed
- Density
- Temperature
- B
- Sunspot Number
- Coronal Hole Area

결과는 `solar_wind_overview.png`로 저장됩니다. 장기 변화, 결측 구간, 비정상적으로 큰 값, public/private 기간의 분포 차이를 눈으로 확인하는 데 사용할 수 있으며 CSV 값은 수정하지 않습니다.

```bash
uv run omni_plot.py
```

## 4. 예측 문제

각 forecast origin `t`에서 그 시점까지 관측된 정보만 이용해 4일 뒤 Speed를 예측합니다.

```text
Target = Speed(t + 4 days)
Forecast horizon = 4-day = 96 hours
```

예를 들어 2023-12-28 00:30까지의 자료로 2024-01-01 00:30의 Speed를 예측합니다.

### Walk-forward 가정

실제 예보에서는 시간이 지나면서 새로운 관측이 순서대로 들어옵니다. 따라서 private를 평가할 때도 각 시점에 이미 관측된 과거값만 사용합니다. 미래 private Speed를 미리 shift하거나 이후 시점의 Density·Temperature·B를 사용하면 안 됩니다.

### 왜 4-day인가?

현재 `Coronal Hole Area` 계산법이 ESWF의 중앙자오선 15° 띠 방식과 유사하고, ESWF 계열 연구에서 CH와 지구 태양풍 사이의 평균 지연을 약 4일로 보고하기 때문입니다.

Public의 단순 CC는 3일에 `0.388`, 4일에 `0.375`로 3일이 조금 높지만 차이는 크지 않습니다. 이 프로젝트에서는 public 결과에 맞춰 horizon을 사후 변경하지 않고, 문헌 및 ESWF와의 비교를 위해 4-day를 사용합니다.

## 5. CSV 변수 설명

| 열 | 단위·의미 | 모델에서의 역할과 주의점 |
|---|---|---|
| `datetime` | UTC 시각, 1시간 간격 | 행 정렬, lag와 target 생성, 시간 split에 사용합니다. |
| `Speed (km/s)` | 지구 근처 태양풍 속도 | 4일 뒤 값은 target이고, forecast origin까지의 과거값은 autoregressive feature로 사용할 수 있습니다. |
| `Density (1/cm^3)` | 태양풍 양성자 수밀도 | CIR/HSS 압축영역과 관련됩니다. |
| `Temperature (K)` | 태양풍 양성자 온도 | 고속 태양풍에서 함께 상승할 수 있습니다. |
| `B (nT)` | 행성간 자기장 크기 | 방향이 없는 total magnitude입니다.|
| `Sunspot Number` | 일별 흑점 수 | 전체 태양활동 수준의 장기 proxy이며 같은 날짜에 반복됩니다. |
| `Coronal Hole Area` | 0–1 사이의 일별 면적 비율 | 매일 00:00 UT 영상에서 계산해 같은 UTC 날짜의 24개 시간 행에 붙였습니다. CH가 없는 `0.0`과 결측치 `NaN`은 다릅니다. |

### Public 결측률

| 열 | 결측 행 | 결측률 |
|---|---:|---:|
| Speed | 452 | 0.397% |
| Density | 1,014 | 0.890% |
| Temperature | 556 | 0.488% |
| B | 272 | 0.239% |
| Sunspot Number | 0 | 0.000% |
| Coronal Hole Area | 720 | 0.632% |

결측률은 낮지만 처리 방식도 모델의 일부입니다.

- Target Speed가 `NaN`인 표본은 학습·평가에서 제외합니다.
- Predictor는 causal forward fill, train-only imputation 또는 NaN을 지원하는 모델을 사용할 수 있습니다.
- 양방향 interpolation처럼 미래값을 이용하는 처리는 피합니다.
- CH가 결측인 날짜에 전날 값을 무기한 전달하지 않습니다.

## 6. Coronal Hole Area 계산법

이 값은 태양 전체의 물리적 면적(km²)이 아니라, **중앙자오선 주변 띠에서 CH로 판정된 픽셀의 비율**입니다.

1. 매일 00:00 UT의 SDO/AIA 193 Å synoptic FITS를 사용합니다.
2. 픽셀을 Heliographic Stonyhurst 경도·위도로 변환합니다.
3. 태양 원반 안에서 경도 ±7.5°, 위도 ±60°인 띠를 선택합니다.
4. 태양 원반 전체 밝기의 중앙값을 계산합니다.
5. 중앙값의 30%보다 어두운 띠 안의 픽셀을 CH로 판정합니다.
6. `CH 픽셀 수 / 띠 전체 픽셀 수`를 일별 면적 비율로 저장합니다.
7. 계산하지 못한 날은 `NaN`으로 둡니다.

따라서 현재 CH 변수는 위치, 형상, 위도별 분포, 자기장 극성을 모두 표현하지 않는 1차원 지표입니다.

### Public CH–Speed correlation

2011–2023에서 `Coronal Hole Area(t)`와 `Speed(t+lag)`의 Pearson CC는 다음과 같습니다.

| Lag | CC |
|---:|---:|
| 0일 | 0.044 |
| 1일 | 0.118 |
| 2일 | 0.267 |
| 3일 | **0.388** |
| 4일 | 0.375 |
| 5일 | 0.253 |
| 6일 | 0.134 |
| 7일 | 0.071 |

48–120시간을 한 시간씩 비교하면 최대값은 약 `82시간(3.42일), CC=0.401`입니다. 이는 CME 제거와 계절 보정을 하지 않은 단순 상관이므로 인과관계나 최종 모델 성능을 의미하지 않습니다.

## 7. ESWF 참고 모델

ESWF(Empirical Solar Wind Forecast)는 중앙자오선 주변 CH 면적과 약 4일 뒤 지구 태양풍 속도의 경험적 관계를 사용합니다.

```text
Coronal Hole Area(t) → Speed(t + 4 days)
```

- [Vršnak et al. (2007)](https://link.springer.com/article/10.1007/s11207-007-0285-8): CH 면적·위치와 HSS 특성
- [Rotter et al. (2015)](https://arxiv.org/abs/1501.06697): 평균 지연 `4.02 ± 0.5일`
- [Reiss et al. (2016)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2016SW001390): Operational ESWF 검증
- [Milošić et al. (2023)](https://link.springer.com/article/10.1007/s11207-022-02102-5): 개선된 ESWF 2.0

현재 CSV는 ESWF 아이디어를 참고했지만 operational ESWF를 완전히 복제한 것은 아닙니다. ESWF는 시간에 따라 변하는 CH 자료와 최근 Carrington rotation을 사용해 경험식의 계수를 갱신합니다.

## 8. Public에서 모델을 개발하는 방법

### Train, validation, test

- **Train**: 모델 계수를 학습합니다.
- **Validation**: feature, 모델, hyperparameter를 선택합니다.
- **Public test**: 선택한 방법을 public의 미래 구간에서 확인합니다.
- **Private test**: public에서 확정한 방법을 2024–2025에서 최종 확인합니다.

### Cross-validation의 의미와 목적

Cross-validation(CV)은 public을 여러 train·validation 조합으로 나누어 반복 평가하는 선택적 방법입니다. 이 프로젝트에서 반드시 사용해야 하는 것은 아닙니다.

- 특정 기간에서 우연히 잘 나온 모델을 고를 위험을 줄입니다.
- 서로 다른 계절과 태양활동 상태에서 모델을 확인합니다.
- Fold별 평균과 표준편차로 성능과 안정성을 함께 비교합니다.

CV는 새로운 데이터를 만드는 data augmentation이 아니며 private test를 대체하지 않습니다. 일반 K-fold처럼 시간을 무작위로 섞으면 미래 자료가 train에 들어갈 수 있으므로 시계열에서는 시간 순서를 고려해야 합니다.

## 9. 사용할 수 있는 split 예시

아래 방법은 가능한 선택지를 설명하기 위한 예시입니다. 모든 split을 반드시 구현하거나 성능을 비교할 필요는 없습니다. 목적과 계산시간에 맞는 방법 하나를 선택하고, 선택 이유와 미래정보 누출 여부를 설명하면 됩니다. 가장 단순한 방법은 S4이고, 조금 더 안정적인 평가가 필요하면 S5를 사용할 수 있습니다.

### S1. Random hourly split

시간 행을 무작위로 나눕니다. 구현은 쉽지만 인접 시점과 동일 날짜의 CH가 train/test에 섞이므로 실제 시계열 forecasting에는 권장하지 않습니다.

### S2. Fixed 8/2/2-month split

모든 연도에서 같은 8개월을 train, 2개월을 validation, 2개월을 test로 사용합니다. Test 계절이 고정되고 같은 연도의 미래 월이 train에 포함될 수 있습니다.

### S3. Shifted 8/2/2-month split

S2의 월 배치를 매년 4개월씩 이동합니다. 계절 편향은 줄지만 같은 연도의 미래 자료로 과거를 평가할 수 있어 실제 미래 예보와는 차이가 있습니다.

### S4. Fixed chronological split

```text
Train:       2011–2019
Validation:  2020–2021
Public test: 2022–2023
```

과거로 학습해 미래를 평가하므로 구현과 설명이 쉽습니다. 한 번의 기간 분할에 결과가 민감할 수 있습니다.

### S5. Expanding-window time-series cross-validation

```text
Fold 1: Train 2011–2016 / Validation 2017 / Test 2018
Fold 2: Train 2011–2017 / Validation 2018 / Test 2019
...
Fold 6: Train 2011–2021 / Validation 2022 / Test 2023
```

학습기간을 점차 늘리면서 항상 미래 연도를 평가합니다. Rolling-origin evaluation 또는 forward-chaining CV라고도 합니다. 시간 순서를 지키면서 여러 미래 구간의 성능 변동을 확인하고 싶을 때 사용할 수 있는 비교적 안정적인 방법입니다.

### Split 경계 주의

4-day target을 만들 때 train 입력에 연결된 정답이 validation/test 기간으로 넘어가면 안 됩니다. Target timestamp 기준으로 표본을 나누거나 각 경계에서 최소 96시간을 제거합니다.

Scaler, imputer, feature selection은 각 fold의 train에서만 `fit`하고 validation/test에는 `transform`만 적용합니다.

## 10. Baseline

### Persistence

- **4-day persistence**: `Speed(t+4일) = Speed(t)`로 예측합니다.
- **27-day persistence**: 태양의 약 27일 자전 재현성을 이용해 target 시점의 27일 전 Speed를 예측값으로 사용합니다.

대표적인 동적 baseline은 27-day persistence이며, 4-day persistence도 기본 sanity check입니다.

### Climatology

Climatology는 현재 변화를 추적하지 않고 과거 Speed의 대표값을 항상 예측하는 방법입니다. 여기서 climatology는 지구 기후가 아니라 **태양풍 속도의 장기 기준 분포**라는 의미입니다.

- Mean climatology: 과거 평균을 항상 예측하며 상수 예측의 RMSE 기준입니다.
- Median climatology: 과거 중앙값을 항상 예측하며 상수 예측의 MAE 기준입니다.

### Private baseline evaluation

아래 표는 모든 baseline을 실제 평가 구간인 **2024–2025 private 전체**에 적용한 결과입니다. Private Speed는 점수 계산과 persistence의 과거 관측값으로만 사용하며, mean·median 산출에는 사용하지 않습니다.

계산 방법은 다음과 같습니다.

1. 평가 target은 `solar_wind-private.csv`의 `2024-01-01 00:30`–`2025-12-31 23:30` Speed입니다.
2. **Public mean**은 2011–2023 public Speed의 `NaN`을 제외한 평균 `417.204... km/s`를 모든 private 시점에 예측합니다.
3. **Public median**은 같은 public Speed의 중앙값 `397.0 km/s`를 모든 private 시점에 예측합니다.
4. **4-day persistence**는 각 private target 시각 `t`에 `prediction(t) = Speed(t - 96 hours)`를 적용합니다.
5. **27-day persistence**는 각 private target 시각 `t`에 `prediction(t) = Speed(t - 648 hours)`를 적용합니다. 두 persistence 모두 같은 분(`:30`)의 timestamp를 직접 대응합니다.
6. Persistence는 고정 학습 모델이 아니라 관측 스트림이 순차적으로 들어오는 **walk-forward model**입니다. 따라서 2024년 1월 초에는 public의 과거 Speed를, 그 이후에는 예측 시점까지 이미 관측된 private Speed도 사용합니다. 미래 Speed는 사용하지 않습니다.
7. Lag 시점의 Speed가 결측이면 그 시점 이전의 마지막 관측값으로 causal forward fill합니다. 그래도 값이 없을 때만 public median을 사용합니다. Target Speed가 `NaN`인 시점은 모든 baseline의 평가에서 공통으로 제외하므로 `N=17,280`입니다.
8. 각 행에서 유효한 관측값 `y_i`와 예측값 `p_i`를 아래 식에 넣고, 표에는 소수 둘째 자리(CC와 Skill은 셋째 자리)로 반올림했습니다.

```text
MAE  = mean(|y_i - p_i|)
RMSE = sqrt(mean((y_i - p_i)^2))
CC   = Pearson correlation(y_i, p_i)
```

| Baseline | N | MAE (km/s) | RMSE (km/s) | CC | MAE Skill vs 27-day |
|---|---:|---:|---:|---:|---:|
| Public mean (`417.20`) | 17,280 | **77.82** | **108.85** | — | **0.025** |
| 27-day persistence | 17,280 | 79.85 | 111.39 | **0.427** | 0.000 |
| Public median (`397.00`) | 17,280 | 80.48 | 115.69 | — | -0.008 |
| 4-day persistence | 17,280 | 104.72 | 137.60 | 0.146 | -0.312 |

Climatology는 HSS 도착 시점을 맞히지 못하고 상수라서 CC도 정의되지 않습니다. 따라서 MAE·RMSE뿐 아니라 CC와 실제 HSS 사례를 함께 확인해야 합니다. 선택한 split에서도 baseline을 같은 test 기간에 다시 계산합니다.

예를 들어 2024-01-01 00:30의 27-day persistence는 2023-12-05 00:30의 public Speed를 사용합니다. `make_baseline_submissions.py`가 네 baseline의 private 예측 CSV를 만들고, `evaluate_submissions.py`가 위 표의 점수와 랭킹을 계산합니다.

## 11. 평가 지표

- **MAE**: 평균적인 예측 오차. 낮을수록 좋습니다.
- **RMSE**: 큰 오차를 더 강하게 벌점합니다. 낮을수록 좋습니다.
- **Pearson CC**: 관측과 예측의 시간적 상승·하강 유사성입니다. 높을수록 좋습니다.
- **MAE Skill vs 27-day persistence**: 모델의 MAE가 대표 baseline보다 얼마나 개선됐는지 나타냅니다.

```text
MAE Skill = 1 - (Model MAE / 27-day persistence MAE)
```

- `Skill > 0`: 27-day persistence보다 좋음
- `Skill = 0`: 27-day persistence와 같음
- `Skill < 0`: 27-day persistence보다 나쁨

Target Speed가 `NaN`인 시점은 평가에서 제외합니다. 모든 모델과 baseline은 같은 target 시점에서 비교합니다.

## 12. 권장 조별 진행 순서

1. Public 데이터와 결측치를 탐색합니다.
2. 4-day target과 causal lag feature를 만듭니다.
3. Baseline을 구현합니다.
4. Public 안에서 사용할 validation split 하나를 정합니다.
5. Public에서 모델과 hyperparameter를 결정합니다.
6. 선택 이유와 public 결과를 기록하고 코드를 저장합니다.
7. 확정 모델을 public 전체로 재학습합니다.
8. Private를 한 번 평가합니다.
9. Public–private 성능 차이, leakage, 계절 및 Solar Cycle 의존성을 토론합니다.

## 13. 최종 결과물

- 재현 가능한 전처리·학습·예측 코드
- 사용한 split, feature, 모델과 선택 이유
- Public baseline 및 모델 비교표
- Private 최종 성능
- Public과 private 성능 차이에 대한 해석
- 한계와 후속 개선 아이디어

## 14. 예시 제출과 평가 코드

다음 명령은 4개 baseline 제출 CSV를 한 번에 만듭니다.

```bash
uv run make_baseline_submissions.py
```

스크립트에는 `make_4_day_persistence_submission`, `make_27_day_persistence_submission`, `make_public_mean_submission`, `make_public_median_submission`의 네 독립 함수가 있습니다. 각 함수는 public/private DataFrame을 입력받고 다른 함수나 전역 계산값을 참조하지 않은 채 아래 두 열의 submission DataFrame을 반환합니다. 새 모델도 같은 입출력 형태의 함수로 만든 뒤 `models` 목록에 추가하면 됩니다.

출력 파일은 `./submissions/`에 저장되며 형식은 다음과 같습니다.

```csv
datetime,predicted_speed
2024-01-01 00:30:00,401.2
2024-01-01 01:30:00,398.7
```

새 모델의 제출 CSV를 평가하려면 `evaluate_submissions.py` 상단의 `SUBMISSION_FILES` 목록에 경로를 추가한 뒤 실행합니다.

```bash
uv run solarwind2/evaluate_submissions.py
```

평가 코드는 모든 CSV를 같은 private target 시점에서 비교하고 MAE가 낮은 순서로 랭킹을 출력합니다. RMSE, CC와 27-day persistence 대비 MAE Skill도 함께 표시하며 결과를 `submissions/evaluation_ranking.csv`에 저장합니다.

## 15. 유사 사례

NOAA/NASA의 [MagNet competition](https://www.drivendata.org/competitions/73/noaa-magnetic-forecasting/)은 실시간 태양풍 자료로 Dst를 예측하고 미래 기간에서 최종 평가했습니다. NASA CCMC의 [SIML-HSS](https://ccmc.gsfc.nasa.gov/models/SIML-HSS~1/)는 코로날 홀과 과거 태양풍을 이용해 4-day solar-wind forecast를 수행합니다.
