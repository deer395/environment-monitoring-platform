"""Generate V1 plot previews for depth and temperature."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_intraday_anomaly
from src.loaders import load_depth_and_temperature
from src.metrics import calculate_metrics
from src.plotting import (
    plot_hourly_daily,
    plot_intraday_anomaly,
    plot_temperature_monthly,
)
from src.qc import apply_quality_control
from src.resampling import resample_daily_mean, resample_hourly_mean
from src.variable_registry import get_variable_metadata


OUTPUT_DIR = PROJECT_ROOT / "outputs"


def run_plot_preview(data_dir=PROJECT_ROOT / "data_private", output_dir=OUTPUT_DIR):
    loaded = load_depth_and_temperature(data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for variable_key, raw in loaded.items():
        metadata = get_variable_metadata(variable_key)
        qc_data, _, _ = apply_quality_control(raw, metadata)
        hourly = resample_hourly_mean(qc_data)
        daily = resample_daily_mean(qc_data)
        anomaly = calculate_intraday_anomaly(hourly, daily)
        metrics = calculate_metrics(variable_key, hourly, daily, anomaly)
        results[variable_key] = metrics

        plot_hourly_daily(
            hourly,
            daily,
            variable_key,
            output_dir / f"{variable_key}_hourly_daily.png",
        )
        plot_intraday_anomaly(
            anomaly,
            variable_key,
            output_dir / f"{variable_key}_intraday_anomaly.png",
        )

    plot_temperature_monthly(
        results["temperature"]["monthly"],
        output_dir / "temperature_monthly_stats.png",
    )

    for path in [
        output_dir / "depth_hourly_daily.png",
        output_dir / "depth_intraday_anomaly.png",
        output_dir / "temperature_hourly_daily.png",
        output_dir / "temperature_intraday_anomaly.png",
        output_dir / "temperature_monthly_stats.png",
    ]:
        print(path)


if __name__ == "__main__":
    run_plot_preview()
