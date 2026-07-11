"""Plotting functions for V1 depth and temperature outputs."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

try:
    from .variable_registry import get_variable_metadata
except ImportError:  # pragma: no cover
    from variable_registry import get_variable_metadata


FIG_SIZE = (11, 5.8)
DPI = 300
TITLE_SIZE = 15
LABEL_SIZE = 12
TICK_SIZE = 10
LEGEND_SIZE = 11
LINE_WIDTH = 1.1
GRID_STYLE = {"linestyle": "--", "linewidth": 0.6, "alpha": 0.35}

plt.rcParams.update(
    {
        "font.size": LABEL_SIZE,
        "axes.titlesize": TITLE_SIZE,
        "axes.labelsize": LABEL_SIZE,
        "legend.fontsize": LEGEND_SIZE,
        "xtick.labelsize": TICK_SIZE,
        "ytick.labelsize": TICK_SIZE,
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
    }
)


def _label(variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", metadata.get("display_name", variable_key))
    unit = metadata.get("unit", "")
    return name, unit


def _apply_y_axis_range(ax, variable_key):
    y_axis_range = get_variable_metadata(variable_key).get("y_axis_range")
    if y_axis_range:
        ax.set_ylim(y_axis_range)


def _prepare_output(output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _new_figure():
    return plt.subplots(figsize=FIG_SIZE)


def _style_axis(ax, title, xlabel, ylabel, show_legend=False):
    ax.set_title(title, fontsize=TITLE_SIZE, pad=12)
    ax.set_xlabel(xlabel, fontsize=LABEL_SIZE)
    ax.set_ylabel(ylabel, fontsize=LABEL_SIZE)
    ax.tick_params(axis="both", labelsize=TICK_SIZE)
    ax.grid(True, **GRID_STYLE)
    if show_legend:
        ax.legend(frameon=False, fontsize=LEGEND_SIZE, loc="best")


def _format_date_axis(ax):
    locator = mdates.AutoDateLocator(minticks=5, maxticks=8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.tick_params(axis="x", rotation=30)


def _save(fig, output_path):
    fig.tight_layout()
    fig.savefig(_prepare_output(output_path), dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def plot_hourly_daily(hourly_df, daily_df, variable_key, output_path):
    """Plot hourly raw series and daily mean series, then save as PNG."""
    name, unit = _label(variable_key)
    fig, ax = _new_figure()
    ax.plot(hourly_df["datetime"], hourly_df["value"], color="#1f77b4", linewidth=0.8, label="原始序列")
    ax.plot(daily_df["datetime"], daily_df["value"], color="#d62728", linewidth=1.5, label="日平均序列")
    _style_axis(ax, f"{name}原始序列与日平均序列", "日期", f"{name}({unit})", show_legend=True)
    _apply_y_axis_range(ax, variable_key)
    _format_date_axis(ax)
    _save(fig, output_path)


def plot_intraday_anomaly(anomaly_df, variable_key, output_path):
    """Plot intra-day anomaly and save as PNG."""
    name, unit = _label(variable_key)
    fig, ax = _new_figure()
    ax.plot(anomaly_df["datetime"], anomaly_df["anomaly"], color="#1f77b4", linewidth=LINE_WIDTH)
    ax.axhline(0, color="#333333", linewidth=0.8, alpha=0.8)
    _style_axis(ax, f"{name}日内距平", "日期", f"{name}距平({unit})")
    _format_date_axis(ax)
    _save(fig, output_path)


def plot_temperature_monthly(monthly_stats_df, output_path):
    """Plot temperature monthly mean with monthly std error bars."""
    data = monthly_stats_df.copy()
    x = data["year_month"].astype(str)
    fig, ax = _new_figure()
    ax.errorbar(
        x,
        data["monthly_mean"],
        yerr=data["monthly_std"],
        fmt="o-",
        color="#d62728",
        ecolor="#666666",
        elinewidth=1,
        capsize=4,
        linewidth=LINE_WIDTH,
        label="月平均 ± 月标准差",
    )
    _style_axis(ax, "温度月平均与月标准差", "年月", "温度(degC)", show_legend=True)
    ax.tick_params(axis="x", rotation=30)
    _save(fig, output_path)
