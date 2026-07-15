"""Deterministic, dependency-free descriptions of report time series."""
from __future__ import annotations
import pandas as pd

TREND_CHANGE_FRACTION = 0.15
HIGH_VARIABILITY_FRACTION = 0.35
CHANGE_POINT_FRACTION = 0.35
MIN_POST_CHANGE_PERIODS = 2
MONTHLY_RELATIVE_CHANGE_FRACTION = 0.15
PERIODIC_AUTOCORRELATION_THRESHOLD = 0.55
MIN_PERIODIC_CYCLES = 6

MODE_LABELS = {"increase": "上升", "decrease": "下降", "stable": "相对稳定", "trend_up": "整体上升", "trend_down": "整体下降", "decrease_then_increase": "先下降后上升", "increase_then_decrease": "先上升后下降", "change_point": "明显转折", "high_variability": "高波动", "periodic": "周期波动", "monthly_pattern": "月际变化", "trend": "长期趋势"}

def chinese_period(value):
    ts = pd.Timestamp(value)
    part = "月初" if ts.day <= 10 else "月中旬" if ts.day <= 20 else "月末"
    return f"{ts.year}年{ts.month}{part}"

def _quantile(series, q):
    values = pd.to_numeric(series, errors="coerce").dropna()
    return values.quantile(q) if not values.empty else pd.NA

def _month_text(value):
    period = pd.Period(str(value), freq="M")
    return f"{period.year}年{period.month}月"


def _periodicity(hourly):
    if hourly is None or len(hourly) < 48 or "datetime" not in hourly:
        return {"detected": False}
    source = hourly[["datetime", "value"]].copy().dropna()
    source["datetime"] = pd.to_datetime(source["datetime"], errors="coerce")
    source = source.dropna().sort_values("datetime")
    interval_hours = source["datetime"].diff().dt.total_seconds().median() / 3600
    if len(source) < 48 or not pd.notna(interval_hours) or interval_hours <= 0:
        return {"detected": False}
    lag = max(2, round(24 / interval_hours))
    if len(source) < lag * MIN_PERIODIC_CYCLES:
        return {"detected": False}
    values = pd.to_numeric(source["value"], errors="coerce")
    corr = values.autocorr(lag=lag)
    half_corr = values.autocorr(lag=max(1, lag // 2))
    detected = bool(pd.notna(corr) and corr >= PERIODIC_AUTOCORRELATION_THRESHOLD and pd.notna(half_corr) and half_corr < .6 and corr - half_corr >= .07)
    return {"detected": detected, "autocorrelation": corr, "half_period_autocorrelation": half_corr, "period_hours": lag * interval_hours}


def _mode(mode, matched, score=0.0, evidence=None, reason=""):
    return {"mode": mode, "is_match": bool(matched), "score": float(score), "evidence": evidence or {}, "reason": reason}


def detect_change_point_mode(monthly):
    data = monthly.dropna(subset=["monthly_mean"]).reset_index(drop=True) if monthly is not None and not monthly.empty else pd.DataFrame()
    if len(data) < MIN_POST_CHANGE_PERIODS + 2: return _mode("change_point", False, reason="monthly data insufficient")
    jumps = data["monthly_mean"].diff().abs(); idx = jumps.idxmax(); pre, post = data.loc[:idx-1, "monthly_mean"].mean(), data.loc[idx:, "monthly_mean"].mean()
    span = data["monthly_mean"].max() - data["monthly_mean"].min(); change = post - pre
    matched = pd.notna(span) and span > 0 and jumps.loc[idx] >= span * CHANGE_POINT_FRACTION and abs(change) >= span * CHANGE_POINT_FRACTION
    evidence = {"change_month": data.loc[idx, "year_month"], "direction": "increase" if change > 0 else "decrease", "pre_mean": pre, "post_mean": post, "absolute_change": abs(change), "relative_change_pct": abs(change / pre * 100) if abs(pre) > 1e-12 else pd.NA, "persistence_count": len(data) - idx}
    return _mode("change_point", matched, abs(change) / span if span else 0, evidence, "largest sustained monthly step")


def detect_trend_mode(daily, p5=pd.NA, p95=pd.NA):
    data = daily.dropna(subset=["value"]).reset_index(drop=True) if daily is not None and not daily.empty else pd.DataFrame()
    if len(data) < 6: return _mode("trend", False, reason="daily data insufficient")
    start, end = data.iloc[:len(data)//3]["value"].mean(), data.iloc[-len(data)//3:]["value"].mean(); change = end - start; span = p95-p5
    slope = (data["value"].iloc[-1] - data["value"].iloc[0]) / max(len(data)-1, 1); matched = pd.notna(span) and span > 0 and abs(change) >= span * TREND_CHANGE_FRACTION
    return _mode("trend", matched, abs(change) / span if span else 0, {"direction": "increase" if change > 0 else "decrease", "start_mean": start, "end_mean": end, "absolute_change": abs(change), "relative_change_pct": abs(change/start*100) if abs(start)>1e-12 else pd.NA, "slope": slope, "duration": len(data)}, "sustained start-end change")


def detect_monthly_pattern_mode(monthly, monthly_interpretation=None):
    data = monthly.dropna(subset=["monthly_mean"]) if monthly is not None and not monthly.empty else pd.DataFrame()
    if len(data) < 3: return _mode("monthly_pattern", False, reason="monthly data insufficient")
    span = data["monthly_mean"].max() - data["monthly_mean"].min(); mean = data["monthly_mean"].mean(); segments = (monthly_interpretation or {}).get("segments", [])
    return _mode("monthly_pattern", bool(len(segments) >= 2 or (abs(mean)>1e-12 and span/abs(mean) >= .12)), min(1, span/(abs(mean)+1e-12)), {"segments": segments, "highest_month": data.loc[data.monthly_mean.idxmax(), "year_month"], "lowest_month": data.loc[data.monthly_mean.idxmin(), "year_month"], "highest_value": data["monthly_mean"].max(), "lowest_value": data["monthly_mean"].min()}, "multi-stage monthly variation")


def detect_high_variability_mode(daily_range, anomaly_abs_p95, p5, p95, max_monthly_std=pd.NA, max_monthly_std_month=None):
    ranges = pd.to_numeric(daily_range.get("daily_range"), errors="coerce") if daily_range is not None else pd.Series(dtype=float)
    median, q95 = _quantile(ranges, .5), _quantile(ranges, .95); span = p95-p5
    score = q95/span if pd.notna(q95) and pd.notna(span) and span > 0 else 0
    return _mode("high_variability", score >= HIGH_VARIABILITY_FRACTION, score, {"daily_range_median": median, "daily_range_p95": q95, "anomaly_abs_p95": anomaly_abs_p95, "max_monthly_std": max_monthly_std, "max_monthly_std_month": max_monthly_std_month}, "daily variation relative to subject range")


def detect_periodic_mode(hourly):
    evidence = _periodicity(hourly)
    return _mode("periodic", evidence.get("detected", False), evidence.get("autocorrelation", 0) or 0, {"approximate_period_hours": evidence.get("period_hours"), "lag_correlation": evidence.get("autocorrelation"), "periodic_strength": evidence.get("autocorrelation"), "period_consistency": evidence.get("half_period_autocorrelation"), "sufficient_length": "period_hours" in evidence}, "fixed-lag autocorrelation")


def detect_stable_mode(results, p5, p95, monthly):
    others = [result for key, result in results.items() if key != "stable"]
    monthly_range = (monthly["monthly_mean"].max() - monthly["monthly_mean"].min()) if monthly is not None and not monthly.empty else 0
    span = p95-p5
    matched = not any(item["is_match"] for item in others) and (not pd.notna(span) or span == 0 or monthly_range <= span * .15)
    return _mode("stable", matched, 1.0 if matched else 0, {"monthly_range": monthly_range, "p5": p5, "p95": p95, "stability_score": 1.0 if matched else 0}, "no competing signal")


def extract_monthly_stages(monthly):
    """Return 2–4 broad, reproducible monthly stages without variable branches."""
    data = monthly.dropna(subset=["monthly_mean"]).reset_index(drop=True).copy() if monthly is not None and not monthly.empty else pd.DataFrame()
    if data.empty: return []
    values = data["monthly_mean"].to_numpy(); span = max(values) - min(values); threshold = max(span * .08, 1e-12)
    smooth = data["monthly_mean"].rolling(3, center=True, min_periods=1).mean().to_numpy()
    directions = ["stable"]
    for i in range(1, len(values)):
        delta = smooth[i] - smooth[i-1]
        directions.append("increase" if delta > threshold else "decrease" if delta < -threshold else "stable")
    groups = []; start = 0
    for i in range(1, len(directions)):
        if directions[i] != directions[i-1]: groups.append((start, i-1)); start = i
    groups.append((start, len(values)-1))
    # Merge noisy one-month direction reversals into an explicit short reversal stage.
    stages = []
    for start, end in groups:
        segment_values = values[start:end+1]; direction = directions[end]
        if start == end and start > 0 and end < len(values)-1 and directions[start-1] == directions[start+1] != direction:
            direction = "short_rebound" if values[start] > values[start-1] else "short_fall"
        stages.append({"start_month": data.loc[start, "year_month"], "end_month": data.loc[end, "year_month"], "start_value": values[start], "end_value": values[end], "mean_value": segment_values.mean(), "direction": direction, "absolute_change": values[end]-values[start], "relative_change_pct": ((values[end]-values[start])/values[start]*100) if abs(values[start]) > 1e-12 else pd.NA})
    while len(stages) > 4:
        # merge the shortest stage with its closest neighbor
        idx = min(range(len(stages)), key=lambda i: abs(stages[i]["end_value"]-stages[i]["start_value"]))
        target = max(0, idx-1) if idx else 1
        left, right = sorted((idx, target)); merged = {**stages[left], "end_month": stages[right]["end_month"], "end_value": stages[right]["end_value"], "mean_value": (stages[left]["mean_value"]+stages[right]["mean_value"])/2, "direction": "stable"}
        stages[left:right+1] = [merged]
    return stages


def extract_time_series_features(hourly, daily, monthly, daily_range, anomaly=None):
    hourly = hourly.copy() if hourly is not None else pd.DataFrame()
    daily = daily.copy() if daily is not None else pd.DataFrame()
    monthly = monthly.copy() if monthly is not None else pd.DataFrame()
    ranges = daily_range.copy() if daily_range is not None else pd.DataFrame()
    values = pd.to_numeric(hourly.get("value"), errors="coerce")
    valid = hourly.loc[values.notna()].copy() if "datetime" in hourly else pd.DataFrame()
    result = {"p5": _quantile(values, .05), "p95": _quantile(values, .95), "narrative_mode": "stable", "variability_mode": None, "monthly_interpretation": {"segments": []}}
    if not valid.empty:
        result.update({"max_value": valid.loc[valid["value"].idxmax(), "value"], "max_time": valid.loc[valid["value"].idxmax(), "datetime"], "min_value": valid.loc[valid["value"].idxmin(), "value"], "min_time": valid.loc[valid["value"].idxmin(), "datetime"]})
    result["daily_range_median"] = _quantile(ranges.get("daily_range", pd.Series(dtype=float)), .5)
    result["daily_range_p95"] = _quantile(ranges.get("daily_range", pd.Series(dtype=float)), .95)
    if not ranges.empty and ranges["daily_range"].notna().any():
        row = ranges.loc[ranges["daily_range"].idxmax()]; result.update({"max_daily_range": row["daily_range"], "max_daily_range_date": row["date"]})
    if not monthly.empty and monthly["monthly_mean"].notna().any():
        means = monthly.dropna(subset=["monthly_mean"]); high, low = means.loc[means["monthly_mean"].idxmax()], means.loc[means["monthly_mean"].idxmin()]
        result.update({"monthly_high_month": high["year_month"], "monthly_high_value": high["monthly_mean"], "monthly_low_month": low["year_month"], "monthly_low_value": low["monthly_mean"]})
        stds = monthly.dropna(subset=["monthly_std"])
        if not stds.empty:
            row = stds.loc[stds["monthly_std"].idxmax()]; result.update({"highest_variability_month": row["year_month"], "highest_monthly_std": row["monthly_std"]})
        means = means.reset_index(drop=True)
        result["monthly_interpretation"].update({"start_month": means.iloc[0]["year_month"], "end_month": means.iloc[-1]["year_month"], "monthly_min": low["monthly_mean"], "monthly_min_month": low["year_month"], "monthly_max": high["monthly_mean"], "monthly_max_month": high["year_month"], "max_std": result.get("highest_monthly_std"), "max_std_month": result.get("highest_variability_month")})
        if len(means) >= MIN_POST_CHANGE_PERIODS + 2:
            deltas = means["monthly_mean"].diff().abs()
            idx = deltas.idxmax()
            span = means["monthly_mean"].max() - means["monthly_mean"].min()
            before = means.loc[:idx - 1, "monthly_mean"].mean()
            after = means.loc[idx:, "monthly_mean"].mean()
            if pd.notna(span) and span > 0 and deltas.loc[idx] >= span * CHANGE_POINT_FRACTION and abs(after - before) >= span * CHANGE_POINT_FRACTION:
                direction = "decrease" if after < before else "increase"
                change = after - before
                relative = change / before * 100 if abs(before) > 1e-12 else pd.NA
                result.update({"narrative_mode": "change_point", "change_time": means.loc[idx, "year_month"], "change_direction": direction, "pre_change_level": before, "post_change_level": after})
                result["monthly_interpretation"].update({"change_month": means.loc[idx, "year_month"], "direction": direction, "pre_period_start": means.iloc[0]["year_month"], "pre_period_end": means.loc[idx - 1, "year_month"], "post_period_start": means.loc[idx, "year_month"], "post_period_end": means.iloc[-1]["year_month"], "pre_mean": before, "post_mean": after, "absolute_change": abs(change), "relative_change_pct": abs(relative) if pd.notna(relative) else pd.NA})
                result["monthly_interpretation"]["segments"] = [{"start_month": means.iloc[0]["year_month"], "end_month": means.loc[idx - 1, "year_month"], "mean_level": before, "direction": "stable"}, {"start_month": means.loc[idx, "year_month"], "end_month": means.iloc[-1]["year_month"], "mean_level": after, "direction": direction}]
        if not result["monthly_interpretation"]["segments"]:
            result["monthly_interpretation"]["segments"] = [{"start_month": means.iloc[0]["year_month"], "end_month": means.iloc[-1]["year_month"], "mean_level": means["monthly_mean"].mean(), "direction": "stable"}]
        result["monthly_interpretation"]["segments"] = extract_monthly_stages(monthly)
    trend_source = daily.dropna(subset=["value"]) if "value" in daily else pd.DataFrame()
    if len(trend_source) >= 6 and result["narrative_mode"] != "change_point":
        first, second = trend_source.iloc[:len(trend_source)//2]["value"].mean(), trend_source.iloc[len(trend_source)//2:]["value"].mean()
        span = result["p95"] - result["p5"]
        change = second - first
        if pd.notna(span) and span > 0 and abs(change) >= span * TREND_CHANGE_FRACTION:
            result["narrative_mode"] = "trend_up" if change > 0 else "trend_down"
            q1, q2, q3 = trend_source.iloc[:len(trend_source)//3]["value"].mean(), trend_source.iloc[len(trend_source)//3:2*len(trend_source)//3]["value"].mean(), trend_source.iloc[2*len(trend_source)//3:]["value"].mean()
            if q2 < q1 and q3 > q2: result["narrative_mode"] = "decrease_then_increase"
            elif q2 > q1 and q3 < q2: result["narrative_mode"] = "increase_then_decrease"
    if pd.notna(result["daily_range_p95"]) and pd.notna(result["p95"]) and pd.notna(result["p5"]) and result["p95"] > result["p5"] and result["daily_range_p95"] >= (result["p95"]-result["p5"])*HIGH_VARIABILITY_FRACTION:
        result["variability_mode"] = "high_variability"
    anomaly_values = pd.to_numeric(anomaly.get("anomaly"), errors="coerce") if anomaly is not None else pd.Series(dtype=float)
    result["anomaly_abs_median"] = _quantile(anomaly_values.abs(), .5)
    result["anomaly_abs_p95"] = _quantile(anomaly_values.abs(), .95)
    periodic = _periodicity(hourly); result["periodicity"] = periodic
    modes = {"periodic": detect_periodic_mode(hourly), "change_point": detect_change_point_mode(monthly), "trend": detect_trend_mode(daily, result["p5"], result["p95"]), "monthly_pattern": detect_monthly_pattern_mode(monthly, result.get("monthly_interpretation")), "high_variability": detect_high_variability_mode(ranges, result["anomaly_abs_p95"], result["p5"], result["p95"], result.get("highest_monthly_std"), result.get("highest_variability_month"))}
    modes["stable"] = detect_stable_mode(modes, result["p5"], result["p95"], monthly)
    priority = {"periodic": 6, "change_point": 5, "trend": 4, "monthly_pattern": 3, "high_variability": 2, "stable": 1}
    matches = [entry for entry in modes.values() if entry["is_match"]]
    chosen = max(matches, key=lambda entry: (priority[entry["mode"]], entry["score"])) if matches else modes["stable"]
    result.update({"primary_mode": chosen["mode"], "secondary_mode": next((entry["mode"] for entry in sorted(matches, key=lambda entry: (priority[entry["mode"]], entry["score"]), reverse=True) if entry["mode"] != chosen["mode"]), None), "mode_scores": {key: value["score"] for key, value in modes.items()}, "mode_evidence": {key: value["evidence"] for key, value in modes.items()}})
    return result
