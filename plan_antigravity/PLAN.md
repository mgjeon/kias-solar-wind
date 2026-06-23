# 4-Day Solar Wind Forecasting — 개발 계획

> 목표: Public(2011–2023)에서 4일 뒤 태양풍 속도 예측 모델을 개발하고, Private(2024–2025)에서 baseline을 이기는 성능을 한 번 확인한다.

## 0. 현재 상태

완성되어 있는 것 (재실행만 하면 되는 인프라):

- 데이터 파이프라인: `omni.py` → `extract_ch_area.py` → `prepare_competition_data.py`
- 결합/분할 CSV: `solar_wind-public.csv`, `solar_wind-private.csv`, `solar_wind_data.csv`
- Baseline 제출 생성: `make_baseline_submissions.py` (4종)
- 평가/랭킹: `evaluate_submissions.py` → `submissions/evaluation_ranking.csv`

**남은 일: baseline을 이기는 forecasting 모델을 개발한다.**

### 이겨야 할 기준선 (Private, N=17,280)

| Baseline | MAE | RMSE | CC | 의미 |
|---|---:|---:|---:|---|
| Public mean (417.20) | **77.82** | **108.85** | — | MAE/RMSE 최저 — **이게 진짜 벽** |
| 27-day persistence | 79.85 | 111.39 | **0.427** | CC 최고 — 시간 변동 추종의 기준 |
| Public median | 80.48 | 115.69 | — | — |
| 4-day persistence | 104.72 | 137.60 | 0.146 | sanity check |

**핵심 관찰**: 상수 예측(public mean)이 MAE 77.82로 가장 낮다. 즉 단순히 평균을 깔면 오차는 작지만 HSS(고속류) 도착을 전혀 못 맞힌다(CC 없음). 27-day persistence는 MAE가 약간 높지만 CC=0.427로 변동을 따라간다.

**따라서 우리 모델의 성공 조건**:
- 1차 목표: MAE < 77.82 **그리고** CC > 0.43 (상수보다 오차 낮으면서 변동도 추종)
- 최소 목표: MAE Skill vs 27-day > 0 (MAE < 79.85)이면서 CC ≥ 0.427

## 1. 예측 문제 정의 (고정)

```
Target = Speed(t + 96h),  forecast origin t에서 관측된 과거 정보만 사용
```

- 1시간 간격, walk-forward. 미래 Speed/Density/Temperature/B를 feature로 쓰면 leakage.
- Target Speed가 NaN인 시점은 학습·평가에서 제외.
- 입력 결측은 causal forward fill 또는 NaN-aware 모델만 허용 (양방향 interpolation 금지).

## 2. Feature 설계

사용 가능한 raw 변수: Speed, Density, Temperature, B(시간별), Sunspot Number, Coronal Hole Area(일별).

| 그룹 | Feature | 근거 |
|---|---|---|
| Autoregressive | Speed의 lag (t, t-24h, t-27d=648h), rolling mean/std (24h, 72h) | 27d persistence가 CC 최고 → 27일 주기성이 강함 |
| CH-driven (핵심) | Coronal Hole Area(t), CH lag/rolling (3–4일 선행) | ESWF 이론. Public CH–Speed CC: 3일 0.388, 4일 0.375 |
| Plasma 상태 | Density, Temperature, B의 최근값/rolling | CIR/HSS 압축영역 신호 |
| 활동 수준 | Sunspot Number (장기 proxy) | solar-cycle 분포 이동 보정 |
| 시간 | 연중 위치(계절), Carrington rotation phase | 계절·자전 주기성 |

주의: CH는 t-96h~t-72h 부근의 값이 target(t+96h가 아니라 origin 기준)과 물리적으로 연결됨 — lag 부호 실수 주의. CH의 `0.0`(CH 없음)과 `NaN`(결측)을 구분.

## 3. Validation Split (선택: S4 → 필요시 S5)

COMPETITION.md §9 기준. **기본은 S4(단순·설명 쉬움)**, 안정성 확인이 필요하면 S5.

- **S4 Fixed chronological**: Train 2011–2019 / Val 2020–2021 / Public test 2022–2023
- **S5 Expanding-window CV**: 6 fold rolling-origin (백업/안정성 검증용)

규칙:
- Target timestamp 기준으로 분할, 경계에서 최소 96h 제거 (target leakage 방지).
- Scaler/imputer/feature selection은 각 fold의 **train에서만 fit**, val/test는 transform만.

## 4. 모델 후보 (단순 → 복잡 순서로)

각 모델은 `(public_data, private_data) -> 제출 DataFrame` 함수로 만들어 `make_baseline_submissions.py`의 `models` 목록에 추가하면 동일 파이프라인으로 평가됨.

1. **M1 — ESWF 회귀 (1차 타깃)**: `Speed(t+4d) ~ CH_area(t)` 선형/비선형 회귀. 가장 단순하고 이론 기반. CC를 끌어올리는 핵심.
2. **M2 — Persistence + CH 보정**: 27-day persistence를 base로 CH 신호로 residual 보정. 강한 baseline을 그대로 활용.
3. **M3 — Gradient Boosting (LightGBM/XGBoost)**: §2 전체 feature. NaN-aware, 비선형 상호작용. MAE·CC 동시 개선 기대.
4. **M4 (optional) — 시계열 NN / CNN-on-CH**: AIA FITS 직접 입력(`extract_ch_area.py --cnn-export`). 시간 대비 이득 클 때만.

권장: M1으로 CC 확보 → M3로 MAE까지 최적화. M4는 여유 있을 때.

## 5. 실행 순서 (COMPETITION.md §12 준수)

1. `uv sync` 후 public EDA: 결측 패턴, CH–Speed lag CC, 분포 확인.
2. `src/features.py` — causal lag/rolling feature + 4-day target 생성 (leakage 단위 테스트 포함).
3. S4 split 구현 (96h 경계 제거).
4. M1 → M3 순으로 public에서 학습·검증, val MAE/CC/RMSE 기록.
5. 모델·hyperparameter·선택 이유를 문서화하고 코드 freeze (`git commit`).
6. 확정 모델을 **public 전체로 재학습**.
7. **Private 1회 평가**: 제출 함수 추가 → `make_baseline_submissions.py` → `evaluate_submissions.py`.
8. Public–private 격차, leakage, 계절/Solar Cycle 의존성 해석.

> Private 평가 전 코드/설정 저장, 평가 후엔 결과 해석만. Private를 보고 모델을 고치면 그것은 test가 아니라 validation이 됨.

## 6. 디렉토리 제안

```
src/
  features.py      # causal feature + target 생성
  splits.py        # S4 / S5
  models/
    m1_eswf.py
    m3_gbm.py
  train.py         # public 학습 + val 평가
  predict.py       # 확정 모델 → 제출 CSV (기존 함수 시그니처 유지)
notebooks/eda.ipynb
PLAN.md            # 이 문서
RESULTS.md         # val/private 성능표 + 해석 (최종 결과물)
```

## 7. 리스크 및 주의

- **Leakage**: lag 부호, split 경계, fold별 fit 범위 — 가장 흔한 실수. feature 코드에 단위 테스트.
- **MAE vs CC 트레이드오프**: MAE만 보면 상수 예측이 이긴다. 두 지표를 항상 같이 본다.
- **분포 이동**: Private(Cycle 25 고활동)는 public과 분포가 다름. Sunspot 등으로 보정하되 과적합 주의.
- **Private 재사용 금지**: 평가는 원칙적으로 1회.

## 8. 최종 결과물 (COMPETITION.md §13)

- 재현 가능한 전처리·학습·예측 코드
- 사용한 split / feature / 모델과 선택 이유
- Public baseline 대비 모델 비교표 + Private 최종 성능
- Public–private 격차 해석, 한계, 후속 개선 아이디어
