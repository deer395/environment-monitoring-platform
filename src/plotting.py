"""Plotting functions for V1/V2 depth and temperature outputs."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import plotly.graph_objects as go

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
        "font.sans-serif": ["Noto Sans CJK SC", "Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
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
    xmin, xmax = ax.get_xlim()
    days = xmax - xmin
    if days > 90:
        formatter = mdates.DateFormatter("%Y/%m")
    elif days > 7:
        formatter = mdates.DateFormatter("%Y/%m/%d")
    else:
        formatter = mdates.DateFormatter("%m/%d %H:%M")
    ax.xaxis.set_major_formatter(formatter)
    ax.tick_params(axis="x", rotation=30)


def _save(fig, output_path):
    fig.tight_layout()
    fig.savefig(_prepare_output(output_path), dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def plot_hourly_daily(hourly_df, daily_df, variable_key, output_path):
    """Plot hourly mean and daily mean series, then save as PNG."""
    name, unit = _label(variable_key)
    fig, ax = _new_figure()
    ax.plot(hourly_df["datetime"], hourly_df["value"], color="#1f77b4", linewidth=1, label="小时平均", zorder=1)
    ax.plot(daily_df["datetime"], daily_df["value"], color="#ff3333", linewidth=2, label="日平均", zorder=2)
    _style_axis(ax, f"{name}小时平均与日平均", "日期", f"{name}({unit})", show_legend=True)
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


def plot_monthly_statistics(monthly_stats_df, variable_key, output_path):
    """Plot monthly mean with monthly std error bars for any registered variable."""
    name, unit = _label(variable_key)
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
    _style_axis(ax, f"{name}月平均与月标准差", "年月", f"{name}({unit})", show_legend=True)
    ax.tick_params(axis="x", rotation=30)
    _save(fig, output_path)


def plot_temperature_monthly(monthly_stats_df, output_path):
    """Backward-compatible temperature monthly plot wrapper."""
    plot_monthly_statistics(monthly_stats_df, "temperature", output_path)


def plot_qc_comparison(raw_df, qc_df, variable_key, output_path):
    """Plot raw series and applied-QC series side by side for algorithm checks."""
    name, unit = _label(variable_key)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), sharex=True, sharey=True)
    axes[0].plot(raw_df["datetime"], raw_df["value"], color="#1f77b4", linewidth=0.8)
    axes[1].plot(qc_df["datetime"], qc_df["value"], color="#d62728", linewidth=0.8)

    y_values = raw_df["value"].dropna()
    if not y_values.empty:
        y_min, y_max = y_values.min(), y_values.max()
        margin = max((y_max - y_min) * 0.05, 1e-6)
        axes[0].set_ylim(y_min - margin, y_max + margin)
        axes[1].set_ylim(y_min - margin, y_max + margin)

    _style_axis(axes[0], f"{name}原始时序", "日期", f"{name}({unit})")
    _style_axis(axes[1], f"{name}自动剔除后时序", "日期", f"{name}({unit})")
    for ax in axes:
        _format_date_axis(ax)
        _apply_y_axis_range(ax, variable_key)
    _save(fig, output_path)


def plot_qc_flags(raw_df, qc_log, variable_key, output_path):
    """Plot raw series and highlight QC flags by rule."""
    name, unit = _label(variable_key)
    fig, ax = _new_figure()
    ax.plot(raw_df["datetime"], raw_df["value"], color="#666666", linewidth=0.8, label="原始序列")
    styles = {
        "sensor_zero": ("#9467bd", "X", "传感器 0 值无效"),
        "hard_range": ("#d62728", "x", "硬范围异常"),
        "physical_range": ("#d62728", "x", "硬范围异常"),
        "hampel": ("#ff7f0e", "o", "hampel"),
        "constant_value": ("#2ca02c", "^", "constant_value"),
    }
    for rule, (color, marker, label) in styles.items():
        flags = qc_log[qc_log["rule"] == rule] if qc_log is not None and not qc_log.empty else qc_log
        if flags is not None and not flags.empty:
            ax.scatter(flags["datetime"], flags["original_value"], color=color, marker=marker, s=30, label=label, zorder=3)
    _style_axis(ax, f"{name}质控标记验证", "日期", f"{name}({unit})", show_legend=True)
    _format_date_axis(ax)
    _apply_y_axis_range(ax, variable_key)
    _save(fig, output_path)


def plot_qc_series(qc_df, variable_key, output_path, title_suffix="质控后时序", color="#d62728", raw_df=None):
    """Plot one QC series with optional raw-data y-axis reference."""
    name, unit = _label(variable_key)
    fig, ax = _new_figure()
    ax.plot(qc_df["datetime"], qc_df["value"], color=color, linewidth=0.8, label=title_suffix)

    y_source = raw_df if raw_df is not None else qc_df
    y_values = y_source["value"].dropna()
    if not y_values.empty:
        y_min, y_max = y_values.min(), y_values.max()
        margin = max((y_max - y_min) * 0.05, 1e-6)
        ax.set_ylim(y_min - margin, y_max + margin)

    _style_axis(ax, f"{name}{title_suffix}", "日期", f"{name}({unit})", show_legend=True)
    _format_date_axis(ax)
    _apply_y_axis_range(ax, variable_key)
    _save(fig, output_path)


def _plotly_axis_range(raw_df, variable_key):
    metadata_range = get_variable_metadata(variable_key).get("y_axis_range")
    if metadata_range:
        return metadata_range
    y_values = raw_df["value"].dropna()
    if y_values.empty:
        return None
    y_min, y_max = y_values.min(), y_values.max()
    margin = max((y_max - y_min) * 0.05, 1e-6)
    return [y_min - margin, y_max + margin]


def _candidate_record_ids(qc_log):
    if qc_log is None or qc_log.empty or "record_id" not in qc_log.columns:
        return set()
    return set(qc_log["record_id"].astype(str))


def _extrema_downsample_frame(data, max_points=5000, keep_record_ids=None):
    if data is None or len(data) <= max_points:
        return data.copy() if data is not None else data

    source = data.copy()
    source["datetime"] = source["datetime"].dt.tz_localize(None) if getattr(source["datetime"].dt, "tz", None) is not None else source["datetime"]
    source["_row_order"] = range(len(source))
    source["_time_ns"] = source["datetime"].astype("int64")
    bins = max(max_points // 2, 1)
    time_min = source["_time_ns"].min()
    time_max = source["_time_ns"].max()
    if time_min == time_max:
        sampled = source.head(max_points).copy()
    else:
        span = time_max - time_min
        source["_time_bin"] = ((source["_time_ns"] - time_min) * bins // (span + 1)).clip(lower=0, upper=bins - 1)
        value_series = source["value"]
        min_indices = value_series.groupby(source["_time_bin"]).idxmin().dropna().astype(int)
        max_indices = value_series.groupby(source["_time_bin"]).idxmax().dropna().astype(int)
        keep_indices = set(min_indices.tolist()) | set(max_indices.tolist()) | {source.index[0], source.index[-1]}
        if keep_record_ids and "record_id" in source.columns:
            ids = {str(item) for item in keep_record_ids}
            keep_indices.update(source.index[source["record_id"].astype(str).isin(ids)].tolist())
        sampled = source.loc[sorted(keep_indices)].copy()
    sampled = sampled.sort_values(["datetime", "_row_order"])
    return sampled.drop(columns=[column for column in ["_row_order", "_time_ns", "_time_bin"] if column in sampled.columns])


def create_qc_candidate_figure(raw_df, qc_log, review_table, variable_key, selectable_raw_df=None):
    """Create an interactive Plotly QC figure with selectable raw records."""
    name, unit = _label(variable_key)
    review = review_table.copy()
    review["record_id"] = review["record_id"].astype(str)
    decision_map = review.set_index("record_id")["user_decision"].to_dict()
    rule_map = review.set_index("record_id")["existing_rule"].to_dict()
    log = qc_log.copy() if qc_log is not None and not qc_log.empty else None
    selectable = selectable_raw_df.copy() if selectable_raw_df is not None else raw_df.copy()
    keep_ids = _candidate_record_ids(log) | set(selectable["record_id"].astype(str))
    background = _extrema_downsample_frame(raw_df, 5000, keep_record_ids=keep_ids)
    selectable["record_id"] = selectable["record_id"].astype(str)
    selectable["datetime_text"] = selectable["datetime"].astype(str)
    selectable["existing_rule"] = selectable["record_id"].map(rule_map).fillna("")
    selectable["user_decision"] = selectable["record_id"].map(decision_map).fillna("undecided")
    selectable_customdata = selectable[["record_id", "datetime_text", "value", "existing_rule", "user_decision"]].to_numpy()

    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=background["datetime"],
            y=background["value"],
            mode="lines",
            name="原始数据",
            line={"color": "#111111", "width": 1.2},
            hoverinfo="skip",
        )
    )
    if selectable_raw_df is not None and not selectable.empty:
        fig.add_trace(
            go.Scattergl(
                x=selectable["datetime"],
                y=selectable["value"],
                mode="lines",
                name="当前检查范围原始线",
                line={"color": "#111111", "width": 1.2},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scattergl(
            x=selectable["datetime"],
            y=selectable["value"],
            mode="markers",
            name="原始数据点",
            marker={"color": "rgba(31, 119, 180, 0.35)", "size": 5},
            customdata=selectable_customdata,
            hovertemplate=(
                "记录ID=%{customdata[0]}<br>"
                "时间=%{customdata[1]}<br>"
                "原始值=%{customdata[2]}<br>"
                "已有规则=%{customdata[3]}<br>"
                "当前决定=%{customdata[4]}<extra></extra>"
            ),
        )
    )
    styles = {
        "sensor_zero": {"color": "#9467bd", "symbol": "x", "name": "传感器 0 值无效"},
        "hard_range": {"color": "#d62728", "symbol": "x", "name": "硬范围异常"},
        "physical_range": {"color": "#d62728", "symbol": "x", "name": "硬范围异常"},
        "hampel": {"color": "#ff7f0e", "symbol": "circle-open", "name": "Hampel 候选"},
        "constant_value": {"color": "#2ca02c", "symbol": "triangle-up-open", "name": "恒定值候选"},
    }
    if log is not None:
        log["record_id"] = log["record_id"].astype(str)
        shown_names = set()
        for rule, style in styles.items():
            flags = log[log["rule"].eq(rule)].copy()
            if flags.empty:
                continue
            flags["user_decision"] = flags["record_id"].map(decision_map).fillna(flags["user_decision"])
            flags["datetime_text"] = flags["datetime"].astype(str)
            customdata = flags[["record_id", "datetime_text", "original_value", "rule", "user_decision"]].to_numpy()
            trace_name = style["name"]
            showlegend = trace_name not in shown_names
            shown_names.add(trace_name)
            fig.add_trace(
                go.Scattergl(
                    x=flags["datetime"],
                    y=flags["original_value"],
                    mode="markers",
                    name=trace_name,
                    showlegend=showlegend,
                    marker={"color": style["color"], "symbol": style["symbol"], "size": 7, "opacity": 0.85, "line": {"width": 1.5}},
                    customdata=customdata,
                    hovertemplate=(
                        "记录ID=%{customdata[0]}<br>"
                        "时间=%{customdata[1]}<br>"
                        "原始值=%{customdata[2]}<br>"
                        "规则=%{customdata[3]}<br>"
                        "用户决定=%{customdata[4]}<extra></extra>"
                    ),
                )
            )
    fig.update_layout(
        title=f"{name}质控交互图",
        xaxis_title="日期",
        yaxis_title=f"{name}({unit})",
        hovermode="closest",
        dragmode="select",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 60, "r": 20, "t": 70, "b": 50},
    )
    fig.update_xaxes(tickformat="%Y/%m/%d")
    fig.update_yaxes(range=_plotly_axis_range(raw_df, variable_key))
    return fig


def create_final_qc_figure(final_qc_data, raw_df, variable_key, removed_count, valid_count):
    """Create an interactive Plotly final_qc_data preview figure."""
    name, unit = _label(variable_key)
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=final_qc_data["datetime"],
            y=final_qc_data["value"],
            mode="lines",
            name="最终质控序列",
            line={"color": "#d62728", "width": 1},
        )
    )
    fig.update_layout(
        title=f"{name}final_qc_data 预览：最终缺测数 {removed_count}，最终有效记录数 {valid_count}",
        xaxis_title="日期",
        yaxis_title=f"{name}({unit})",
        hovermode="x unified",
        margin={"l": 60, "r": 20, "t": 70, "b": 50},
    )
    fig.update_xaxes(tickformat="%Y/%m/%d")
    fig.update_yaxes(range=_plotly_axis_range(final_qc_data, variable_key))
    return fig
