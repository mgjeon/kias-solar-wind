"""지정한 제출 CSV들을 평가하고 MAE 기준 랭킹을 출력한다."""

from pathlib import Path

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# 1. 평가할 CSV 목록: 새 제출 파일을 여기에 추가하면 된다
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PRIVATE_CSV = HERE / "solar_wind-private.csv"

SUBMISSION_FILES = [
    HERE / "submissions/baseline_4_day_persistence.csv",
    HERE / "submissions/baseline_27_day_persistence.csv",
    HERE / "submissions/baseline_public_mean.csv",
    HERE / "submissions/baseline_public_median.csv",
]

RANKING_CSV = HERE / "submissions/evaluation_ranking.csv"
SKILL_REFERENCE = "baseline_27_day_persistence"

DATETIME_COLUMN = "datetime"
TARGET_COLUMN = "Speed (km/s)"
PREDICTION_COLUMN = "predicted_speed"


# -----------------------------------------------------------------------------
# 2. Private 정답을 읽는다
# -----------------------------------------------------------------------------
truth = pd.read_csv(
    PRIVATE_CSV,
    usecols=[DATETIME_COLUMN, TARGET_COLUMN],
    parse_dates=[DATETIME_COLUMN],
)

if truth[DATETIME_COLUMN].duplicated().any():
    raise ValueError("Private CSV에 중복 datetime이 있습니다.")


# -----------------------------------------------------------------------------
# 3. 제출 파일을 하나씩 같은 방식으로 평가한다
# -----------------------------------------------------------------------------
results = []

for submission_path in SUBMISSION_FILES:
    submission = pd.read_csv(submission_path, parse_dates=[DATETIME_COLUMN])

    required_columns = {DATETIME_COLUMN, PREDICTION_COLUMN}
    if not required_columns.issubset(submission.columns):
        raise ValueError(
            f"{submission_path.name}: 필요한 열은 {sorted(required_columns)}입니다."
        )

    if submission[DATETIME_COLUMN].duplicated().any():
        raise ValueError(f"{submission_path.name}: 중복 datetime이 있습니다.")

    # Private와 제출 CSV가 정확히 같은 시각을 포함하는지 확인한다.
    if set(submission[DATETIME_COLUMN]) != set(truth[DATETIME_COLUMN]):
        raise ValueError(f"{submission_path.name}: private와 datetime 목록이 다릅니다.")

    comparison = truth.merge(
        submission[[DATETIME_COLUMN, PREDICTION_COLUMN]],
        on=DATETIME_COLUMN,
        how="left",
        validate="one_to_one",
    )

    # 실제 target이 없는 시점은 모든 모델의 평가에서 공통으로 제외한다.
    comparison = comparison.dropna(subset=[TARGET_COLUMN])

    if comparison[PREDICTION_COLUMN].isna().any():
        raise ValueError(f"{submission_path.name}: 예측값에 NaN이 있습니다.")

    actual = comparison[TARGET_COLUMN]
    predicted = comparison[PREDICTION_COLUMN]
    error = predicted - actual

    mae = error.abs().mean()
    rmse = np.sqrt((error**2).mean())

    # 상수 예측은 표준편차가 0이므로 correlation을 정의할 수 없다.
    if predicted.nunique() == 1:
        cc = np.nan
    else:
        cc = actual.corr(predicted)

    results.append(
        {
            "submission": submission_path.stem,
            "N": len(comparison),
            "MAE": mae,
            "RMSE": rmse,
            "CC": cc,
        }
    )


# -----------------------------------------------------------------------------
# 4. 27-day persistence 대비 MAE Skill을 계산한다
# -----------------------------------------------------------------------------
ranking = pd.DataFrame(results)

reference_rows = ranking[ranking["submission"] == SKILL_REFERENCE]
if len(reference_rows) != 1:
    raise ValueError(
        f"MAE Skill 계산을 위해 {SKILL_REFERENCE}.csv를 목록에 포함해야 합니다."
    )

reference_mae = reference_rows.iloc[0]["MAE"]
ranking["MAE_skill_vs_27d"] = 1 - ranking["MAE"] / reference_mae


# -----------------------------------------------------------------------------
# 5. MAE가 낮은 순서로 랭킹을 출력하고 CSV로 저장한다
# -----------------------------------------------------------------------------
ranking = ranking.sort_values(
    ["MAE", "RMSE"],
    ascending=[True, True],
    ignore_index=True,
)
ranking.insert(0, "rank", range(1, len(ranking) + 1))

print("\n=== Private Ranking: lower MAE is better ===")
print(
    ranking.to_string(
        index=False,
        na_rep="—",
        formatters={
            "MAE": "{:.2f}".format,
            "RMSE": "{:.2f}".format,
            "CC": "{:.3f}".format,
            "MAE_skill_vs_27d": "{:.3f}".format,
        },
    )
)

ranking.to_csv(RANKING_CSV, index=False)
print(f"\n랭킹 저장: {RANKING_CSV}")
