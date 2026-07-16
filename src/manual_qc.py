"""Manual QC decision helpers for V2 stage 4."""

import pandas as pd


LOG_COLUMNS = [
    "record_id",
    "datetime",
    "variable",
    "original_value",
    "qc_value",
    "rule",
    "reason",
    "is_flagged",
    "is_applied",
    "parameter",
    "user_decision",
    "decision_source",
]

ALGORITHM_RULES = {"hampel", "constant_value"}
REVIEW_DECISIONS = ["undecided", "keep", "remove", "manual_remove", "manual_keep"]


def summarize_candidate_decisions(review_table):
    """Summarize unique algorithm candidates and their actual user decisions."""
    empty = {"unique_candidate_count": 0, "candidate_removed_count": 0, "candidate_kept_count": 0, "candidate_undecided_count": 0, "manual_extra_removed_count": 0, "hampel_candidate_count": 0, "constant_candidate_count": 0}
    if review_table is None or review_table.empty: return empty
    table = review_table.copy(); flags = table.get("algorithm_flag", pd.Series("", index=table.index)).fillna("").astype(str)
    empty["hampel_candidate_count"] = int(flags.str.contains("hampel").sum()); empty["constant_candidate_count"] = int(flags.str.contains("constant_value").sum())
    candidates = table[flags.ne("")].drop_duplicates("record_id", keep="last").copy(); decisions = candidates.get("user_decision", pd.Series("undecided", index=candidates.index)).fillna("undecided")
    empty["unique_candidate_count"] = len(candidates); empty["candidate_removed_count"] = int(decisions.isin(["remove", "manual_remove"]).sum()); empty["candidate_kept_count"] = int(decisions.isin(["keep", "manual_keep"]).sum()); empty["candidate_undecided_count"] = int((~decisions.isin(["remove", "manual_remove", "keep", "manual_keep"])).sum())
    non_candidate = table[flags.eq("")]; empty["manual_extra_removed_count"] = int(non_candidate.get("user_decision", pd.Series("", index=non_candidate.index)).isin(["manual_remove"]).sum())
    return empty


def _empty_log():
    return pd.DataFrame(columns=LOG_COLUMNS)


def ensure_record_id(data):
    """Return a copy with a stable string record_id column."""
    result = data.copy()
    if "record_id" not in result.columns:
        result.insert(0, "record_id", [f"rec_{idx}" for idx in range(len(result))])
    result["record_id"] = result["record_id"].astype(str)
    return result


def _normalize_datetime_values(values):
    if values is None:
        return []
    return [pd.Timestamp(value) for value in values]


def _normalize_log(qc_log):
    base_log = qc_log.copy() if qc_log is not None and not qc_log.empty else _empty_log()
    for column in LOG_COLUMNS:
        if column not in base_log.columns:
            base_log[column] = pd.NA
    base_log = base_log[LOG_COLUMNS].copy().astype("object")
    base_log["record_id"] = base_log["record_id"].astype("string")
    base_log["datetime"] = pd.to_datetime(base_log["datetime"], errors="coerce")
    base_log.loc[base_log["rule"].isin(["sensor_zero", "hard_range", "physical_range"]), "decision_source"] = "automatic"
    base_log.loc[base_log["rule"].isin(ALGORITHM_RULES), "decision_source"] = "algorithm_suggestion"
    return base_log


def candidate_decision_table(qc_log):
    """Return editable algorithm candidate rows with keep/remove/undecided decisions."""
    table = _normalize_log(qc_log)
    table = table[table["rule"].isin(ALGORITHM_RULES)].copy()
    if table.empty:
        return pd.DataFrame(columns=LOG_COLUMNS)
    table["user_decision"] = table["user_decision"].fillna("undecided")
    table.loc[~table["user_decision"].isin(["keep", "remove", "undecided"]), "user_decision"] = "undecided"
    table["decision_source"] = "algorithm_suggestion"
    return table[LOG_COLUMNS].sort_values(["rule", "datetime", "record_id"]).reset_index(drop=True)


def _rules_by_record_id(qc_log):
    log = _normalize_log(qc_log)
    if log.empty:
        return {}
    return log.groupby("record_id")["rule"].apply(lambda values: ",".join(sorted(set(values.dropna())))).to_dict()


def build_qc_review_table(raw_data, auto_qc_data, qc_log, previous_decisions=None):
    """Build the editable per-record QC review table used by the Streamlit workflow."""
    raw = ensure_record_id(raw_data)[["record_id", "datetime", "value"]].copy()
    raw["datetime"] = pd.to_datetime(raw["datetime"], errors="coerce")
    raw = raw.rename(columns={"value": "original_value"})

    auto = ensure_record_id(auto_qc_data)[["record_id", "value"]].copy()
    auto = auto.rename(columns={"value": "current_qc_value"})

    table = raw.merge(auto, on="record_id", how="left")
    rule_map = _rules_by_record_id(qc_log)
    table["existing_rule"] = table["record_id"].map(rule_map).fillna("")
    table["algorithm_flag"] = table["existing_rule"].map(
        lambda rules: ",".join(rule for rule in ALGORITHM_RULES if rule in str(rules).split(","))
    )
    table["user_decision"] = "undecided"
    hard_mask = table["existing_rule"].str.contains("sensor_zero|hard_range|physical_range", na=False)
    table.loc[hard_mask, "user_decision"] = "remove"

    if previous_decisions is not None and not previous_decisions.empty:
        previous = previous_decisions[["record_id", "user_decision"]].copy()
        previous["record_id"] = previous["record_id"].astype(str)
        previous = previous.drop_duplicates("record_id", keep="last")
        table = table.merge(previous, on="record_id", how="left", suffixes=("", "_previous"))
        mask = table["user_decision_previous"].isin(REVIEW_DECISIONS)
        table.loc[mask, "user_decision"] = table.loc[mask, "user_decision_previous"]
        table = table.drop(columns=["user_decision_previous"])

    return table[["record_id", "datetime", "original_value", "existing_rule", "algorithm_flag", "current_qc_value", "user_decision"]]


def decision_summary(review_table, final_qc_data, auto_qc_data):
    """Return counts used to verify whether decisions reached final_qc_data."""
    candidates = review_table[review_table["algorithm_flag"].astype(str).ne("")]
    auto_missing = int(auto_qc_data["value"].isna().sum())
    final_missing = int(final_qc_data["value"].isna().sum())
    return {
        "候选总数": int(len(candidates)),
        "remove 数量": int(review_table["user_decision"].eq("remove").sum()),
        "keep 数量": int(review_table["user_decision"].eq("keep").sum()),
        "undecided 数量": int(review_table["user_decision"].eq("undecided").sum()),
        "最终实际删除数量": final_missing,
        "用户新增删除数量": max(final_missing - auto_missing, 0),
        "最终有效记录数": int(final_qc_data["value"].notna().sum()),
    }


def apply_review_table_decisions(raw_data, auto_qc_data, qc_log, review_table):
    """Apply the unified review table by record_id and return final_qc_data plus final_qc_log."""
    raw = ensure_record_id(raw_data)
    raw["datetime"] = pd.to_datetime(raw["datetime"], errors="coerce")
    final = ensure_record_id(auto_qc_data)
    final["datetime"] = pd.to_datetime(final["datetime"], errors="coerce")
    variable = final.attrs.get("variable_key") or raw.attrs.get("variable_key")

    base_log = _normalize_log(qc_log)
    review = build_qc_review_table(raw, final, qc_log) if review_table is None else review_table.copy()
    review["record_id"] = review["record_id"].astype(str)
    review["datetime"] = pd.to_datetime(review["datetime"], errors="coerce")
    review["existing_rule"] = review["existing_rule"].fillna("").astype(str)
    review["algorithm_flag"] = review["algorithm_flag"].fillna("").astype(str)
    review["user_decision"] = review["user_decision"].fillna("undecided")

    raw_values = raw.set_index("record_id")["value"]
    final_index = final.set_index("record_id", drop=False)
    aligned = review.set_index("record_id", drop=False)
    aligned["original_value"] = aligned.index.map(raw_values)

    physical = aligned["existing_rule"].str.contains("sensor_zero|hard_range|physical_range", na=False)
    algorithm = aligned["algorithm_flag"].ne("")
    decision = aligned["user_decision"]

    restore_mask = decision.isin(["keep", "undecided", "manual_keep"]) & ~physical
    remove_mask = ((algorithm & decision.eq("remove")) | decision.eq("manual_remove") | (decision.eq("remove") & ~algorithm)) & ~physical
    physical_remove_mask = physical

    if restore_mask.any():
        ids = aligned.index[restore_mask]
        final_index.loc[ids, "value"] = aligned.loc[ids, "original_value"].to_numpy()
    if remove_mask.any():
        final_index.loc[aligned.index[remove_mask], "value"] = pd.NA
    if physical_remove_mask.any():
        final_index.loc[aligned.index[physical_remove_mask], "value"] = pd.NA

    final = final_index.reset_index(drop=True)

    if not base_log.empty:
        base_log = base_log.copy()
        base_log["record_id"] = base_log["record_id"].astype(str)
        decision_map = aligned["user_decision"].to_dict()
        original_map = aligned["original_value"].to_dict()
        physical_ids = set(aligned.index[physical])
        base_log["user_decision"] = base_log["record_id"].map(decision_map).fillna(base_log["user_decision"])
        keep_ids = set(aligned.index[decision.eq("keep") & ~physical])
        remove_ids = set(aligned.index[decision.eq("remove") & algorithm & ~physical])
        base_log.loc[base_log["record_id"].isin(keep_ids), "qc_value"] = base_log.loc[base_log["record_id"].isin(keep_ids), "record_id"].map(original_map)
        base_log.loc[base_log["record_id"].isin(remove_ids | physical_ids), "qc_value"] = pd.NA
        base_log.loc[base_log["record_id"].isin(physical_ids), "user_decision"] = "remove"

    manual_rows = []
    manual_remove_rows = aligned[decision.eq("manual_remove") & ~physical]
    manual_keep_rows = aligned[decision.eq("manual_keep") & ~physical]
    if not manual_remove_rows.empty:
        manual = manual_remove_rows.reset_index(drop=True)[["record_id", "datetime", "original_value"]].copy()
        manual["variable"] = variable
        manual["qc_value"] = pd.NA
        manual["rule"] = "manual_remove"
        manual["reason"] = "用户人工判定"
        manual["is_flagged"] = True
        manual["is_applied"] = True
        manual["parameter"] = "manual"
        manual["user_decision"] = "manual_remove"
        manual["decision_source"] = "user_manual"
        manual_rows.append(manual[LOG_COLUMNS])
    if not manual_keep_rows.empty:
        manual = manual_keep_rows.reset_index(drop=True)[["record_id", "datetime", "original_value"]].copy()
        manual["variable"] = variable
        manual["qc_value"] = manual["original_value"]
        manual["rule"] = "manual_keep"
        manual["reason"] = "用户人工判定"
        manual["is_flagged"] = True
        manual["is_applied"] = True
        manual["parameter"] = "manual"
        manual["user_decision"] = "manual_keep"
        manual["decision_source"] = "user_manual"
        manual_rows.append(manual[LOG_COLUMNS])

    logs = []
    if not base_log.empty:
        logs.append(base_log[LOG_COLUMNS])
    logs.extend(manual_rows)
    final_log = pd.concat(logs, ignore_index=True) if logs else _empty_log()
    if not final_log.empty:
        final_log = final_log[LOG_COLUMNS].sort_values(["datetime", "record_id", "rule"]).reset_index(drop=True)
        raw_value_map = raw.set_index("record_id")["value"]
        deleted_ids = set(final.loc[final["value"].isna() & final["record_id"].map(raw_value_map).notna(), "record_id"].astype(str))
        final_log["is_applied"] = False
        keep_mask = ~final_log["record_id"].astype(str).isin(deleted_ids)
        final_log.loc[keep_mask, "qc_value"] = final_log.loc[keep_mask, "original_value"]
        priority = {"sensor_zero": 0, "hard_range": 1, "physical_range": 1, "manual_remove": 2, "hampel": 3, "constant_value": 4}
        if deleted_ids:
            final_log["_priority"] = final_log["rule"].map(priority).fillna(99)
            applied_index = (
                final_log[final_log["record_id"].astype(str).isin(deleted_ids)]
                .sort_values(["record_id", "_priority"])
                .drop_duplicates("record_id")
                .index
            )
            final_log.loc[applied_index, "is_applied"] = True
            final_log = final_log.drop(columns=["_priority"])

    final.attrs.update(auto_qc_data.attrs)
    return final, final_log


def apply_manual_qc_decisions(raw_data, auto_qc_data, qc_log, candidate_decisions=None, manual_remove_datetimes=None, manual_keep_datetimes=None):
    """Backward-compatible wrapper for older preview scripts."""
    raw = ensure_record_id(raw_data)
    auto = ensure_record_id(auto_qc_data)
    review = build_qc_review_table(raw, auto, qc_log)

    if candidate_decisions is not None and not candidate_decisions.empty:
        decisions = candidate_decisions.copy()
        if "record_id" not in decisions.columns:
            decisions = decisions.merge(review[["record_id", "datetime"]], on="datetime", how="left")
        decisions["record_id"] = decisions["record_id"].astype(str)
        updates = decisions.drop_duplicates("record_id", keep="last").set_index("record_id")["user_decision"].to_dict()
        mask = review["record_id"].isin(updates.keys())
        review.loc[mask, "user_decision"] = review.loc[mask, "record_id"].map(updates)

    if manual_remove_datetimes:
        remove_times = set(_normalize_datetime_values(manual_remove_datetimes))
        review.loc[review["datetime"].isin(remove_times), "user_decision"] = "manual_remove"
    if manual_keep_datetimes:
        keep_times = set(_normalize_datetime_values(manual_keep_datetimes))
        review.loc[review["datetime"].isin(keep_times), "user_decision"] = "manual_keep"

    return apply_review_table_decisions(raw, auto, qc_log, review)
