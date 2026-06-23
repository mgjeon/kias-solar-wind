"""네 baseline 모델로 private 예측 제출 CSV를 만든다.

각 모델 함수는 public/private DataFrame만 입력받고 제출 형식의 DataFrame을
반환한다. 함수끼리 helper나 계산 결과를 공유하지 않으므로 하나씩 독립적으로
읽고 다른 예측 모델의 제출 코드로 바꾸어 볼 수 있다.
"""

from pathlib import Path

import pandas as pd


def make_4_day_persistence_submission(public_data, private_data):
    """각 private 시점에 정확히 96시간 전의 Speed를 예측한다."""
    # Public 뒤에 private 관측 스트림이 순서대로 들어온다고 가정한다.
    history = pd.concat(
        [
            public_data[["datetime", "Speed (km/s)"]],
            private_data[["datetime", "Speed (km/s)"]],
        ],
        ignore_index=True,
    ).sort_values("datetime")

    # 결측치는 미래값을 보지 않고 직전 관측값으로만 채운다.
    speed_history = history.set_index("datetime")["Speed (km/s)"].ffill()
    target_times = private_data["datetime"]
    input_times = target_times - pd.Timedelta(hours=96)
    predictions = speed_history.reindex(input_times).to_numpy()

    # 자료 시작점 등의 이유로 과거값이 전혀 없을 때만 public 중앙값을 쓴다.
    public_median = public_data["Speed (km/s)"].median()
    predictions = pd.Series(predictions).fillna(public_median).to_numpy()

    return pd.DataFrame(
        {"datetime": target_times, "predicted_speed": predictions}
    )


def make_27_day_persistence_submission(public_data, private_data):
    """각 private 시점에 정확히 648시간(27일) 전의 Speed를 예측한다."""
    history = pd.concat(
        [
            public_data[["datetime", "Speed (km/s)"]],
            private_data[["datetime", "Speed (km/s)"]],
        ],
        ignore_index=True,
    ).sort_values("datetime")

    speed_history = history.set_index("datetime")["Speed (km/s)"].ffill()
    target_times = private_data["datetime"]
    input_times = target_times - pd.Timedelta(hours=24 * 27)
    predictions = speed_history.reindex(input_times).to_numpy()

    public_median = public_data["Speed (km/s)"].median()
    predictions = pd.Series(predictions).fillna(public_median).to_numpy()

    return pd.DataFrame(
        {"datetime": target_times, "predicted_speed": predictions}
    )


def make_public_mean_submission(public_data, private_data):
    """Public 전체의 평균 Speed를 모든 private 시점에 예측한다."""
    public_mean = public_data["Speed (km/s)"].mean()

    return pd.DataFrame(
        {
            "datetime": private_data["datetime"],
            "predicted_speed": public_mean,
        }
    )


def make_public_median_submission(public_data, private_data):
    """Public 전체의 중앙값 Speed를 모든 private 시점에 예측한다."""
    public_median = public_data["Speed (km/s)"].median()

    return pd.DataFrame(
        {
            "datetime": private_data["datetime"],
            "predicted_speed": public_median,
        }
    )


def main():
    here = Path(__file__).resolve().parent
    public_csv = here / "solar_wind-public.csv"
    private_csv = here / "solar_wind-private.csv"
    output_dir = here / "submissions"

    public_data = pd.read_csv(public_csv, parse_dates=["datetime"])
    private_data = pd.read_csv(private_csv, parse_dates=["datetime"])

    # 새 모델도 (public_data, private_data) -> submission DataFrame 함수로 만든 뒤
    # 이 목록에 추가하면 같은 형식의 CSV로 저장할 수 있다.
    models = [
        ("baseline_4_day_persistence.csv", make_4_day_persistence_submission),
        ("baseline_27_day_persistence.csv", make_27_day_persistence_submission),
        ("baseline_public_mean.csv", make_public_mean_submission),
        ("baseline_public_median.csv", make_public_median_submission),
    ]

    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, model in models:
        submission = model(public_data, private_data)
        output_path = output_dir / filename
        submission.to_csv(
            output_path,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
        )
        print(f"저장: {output_path} ({len(submission):,} rows)")

    print(
        f"\nPublic mean   : {public_data['Speed (km/s)'].mean():.2f} km/s"
    )
    print(
        f"Public median : {public_data['Speed (km/s)'].median():.2f} km/s"
    )


if __name__ == "__main__":
    main()
