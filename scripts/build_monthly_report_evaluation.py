"""CLI entrypoint for monthly report interpretation evaluation materials."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Allow the documented ``python scripts/...`` command from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.monthly_evaluation_dataset import scan_monthly_workbooks
from src.monthly_evaluation_export import export_all

def main() -> int:
    parser = argparse.ArgumentParser(description="Build monthly report evaluation materials.")
    parser.add_argument("--input-dir", required=True); parser.add_argument("--output-dir", default="evaluation/monthly")
    args = parser.parse_args(); samples, warnings, workbook_count = scan_monthly_workbooks(args.input_dir)
    outputs = export_all(samples, warnings, args.output_dir)
    stations = len({sample["station_name"] for sample in samples})
    print(f"扫描工作簿数：{workbook_count}\n成功识别站点数：{stations}\n成功样本数：{len(samples)}\n跳过样本数：{len(warnings)}\n图件数：{outputs['figures']}")
    print("输出文件：" + ", ".join(str(outputs[key]) for key in ("manifest", "baseline", "annotation", "review")))
    for warning in warnings: print(f"警告 [{warning['workbook_name']} / {warning['variable_key']}] {warning['reason']}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
