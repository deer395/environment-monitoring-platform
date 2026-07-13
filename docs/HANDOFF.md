# 当前分支

feature/v3-general-variables

# 当前已完成

- V2 质量控制闭环；
- V3 架构审计；
- V3.1 通用变量架构；
- V3.2 接入 salinity、dissolved_oxygen、cod；
- V3.2.1 完成 hard_range 与候选图背景线修复；
- V3.3 接入 bod、nitrate、chlorophyll、pahs；
- 通用 loader；
- 通用 metrics；
- 动态导出；
- 不同变量 session_state 隔离；
- 所有已支持变量执行完整分析链。

# 当前 Git 基线

- V2 标签：v2-qc-complete
- V3.1 标签：v3.1-generic-architecture
- V3.2 标签：v3.2-three-variable-validation
- V3.2.1 标签：v3.2.1-qc-interaction-complete

# 当前全部已支持变量

- depth（水深）
- temperature（温度）
- salinity（盐度）
- dissolved_oxygen（溶解氧）
- cod（化学需氧量）
- bod（生化需氧量）
- nitrate（硝酸盐）
- chlorophyll（叶绿素）
- pahs（多环芳烃）

# V3.3 说明

- V3.3 新增变量均通过 src/variable_registry.py 和通用 loader 接入；
- BOD、硝酸盐、叶绿素、多环芳烃真实样例文件位于 data_private；
- 叶绿素 chlorophyll 当前采用 hard_min=0、hard_max=100；
- chlorophyll 的 hard_max=100 是当前项目基于样本分布确定的操作性自动质控上限，不是所有海域和仪器通用的物理上限；
- BOD、nitrate、PAHs 暂定 hard_min=0、hard_max=100，后续需按仪器量程或现场资料复核；
- 样例 Excel 未提供单位列，PAHs 单位仍需确认。

# 下一步

- 运行 src/v3_3_remaining_variables_preview.py 完成 V3.3 全变量回归；
- 测试通过后可按用户要求保存本地 Git 版本；
- 获得仪器量程后复核各变量 hard_range；
- V4 再开始调和分析。

# 当前禁止

- 不实现调和分析；
- 不实现自动报告；
- 不修改 V2 质控算法；
- 不修改日内距平定义。
