# 月际报告解读质量评估

在仓库根目录运行：

`python scripts/build_monthly_report_evaluation.py --input-dir "evaluation_input_private" --output-dir "evaluation/monthly"`

`evaluation_input_private/` 是本地私有输入目录，不进入 Git；生成的清单、盲标图、标注表、基线结果和人工评价输出也均由 `.gitignore` 排除。

先只查看 `figures/blind/` 中的盲标图，在 `annotation_template.xlsx` 的“月际标注”填写 `human_*` 字段。完成独立判断后，才查看 `baseline_review.xlsx`，再填写基线评价字段。

月标准差表示月内波动，不代表月平均趋势；不要对环境成因作解释。`development` 可用于后续调算法，`holdout` 不用于调参。
