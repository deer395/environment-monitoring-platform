# 当前分支

feature/v3-general-variables

# 当前已完成

- V2 质量控制闭环；
- V3 架构审计；
- V3.1 通用变量架构；
- 去除主要 depth/temperature 硬编码；
- 通用 loader；
- 通用 metrics；
- 动态导出；
- 不同变量 session_state 隔离；
- 所有变量执行完整分析链。

# 当前 Git 基线

- V2 标签：v2-qc-complete
- V3.1 标签：v3.1-generic-architecture

# 下一步

V3.2 新变量验证。

第一批变量：

- salinity
- dissolved oxygen
- COD

目标：

- 只通过 registry 和必要的别名配置接入；
- 能上传；
- 能物理范围质控；
- 能 Hampel 和 constant_value 标记；
- 能人工删除、保留和恢复；
- 能生成 hourly、daily、anomaly、daily range、monthly、基础统计；
- 能导出结果；
- 不破坏 depth 和 temperature。

# 当前禁止

- 不一次加入全部变量；
- 不实现调和分析；
- 不实现自动报告；
- 不修改 V2 质控算法；
- 不修改日内距平定义。
