# 当前版本说明

## 当前版本

当前版本：V2 质量控制版本

## 已完成

- depth、temperature 变量注册表
- physical_range
- Hampel
- constant_value
- qc_data、qc_summary、qc_log
- record_id
- Plotly 人工选点
- keep/remove/manual_remove/manual_keep
- final_qc_data
- 质控确认后分析
- QC 日志导出
- 缓存和性能优化

## 当前已知问题

- 绘图主题尚未完全集中管理
- metrics.py 仍有变量硬编码
- 大数据 Plotly 仍可能存在性能压力
- V3 多变量架构尚未开始

## 下一步

- 先进行 V3 架构审计
- 再开始通用变量框架改造
