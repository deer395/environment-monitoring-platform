# Development 18样本盲标审计报告

## 完成情况
- 完成样本数：**18/18**
- 规范版本：**annotation_guideline_v1.md**
- 标注日期：2026-07-17

---

## 各primary_pattern数量

| 类别 | 数量 | 样本 |
|---|---|---|
| stable | 2 | 西霞口叶绿素, 西霞口水深 |
| decreasing | 2 | 西霞口硝酸盐, 北海水深 |
| rise_then_fall | 4 | 北海溶解氧, 北海COD, 威海溶解氧, 威海叶绿素, 西霞口盐度 |
| fall_then_rise | 3 | 北海温度, 北海盐度, 西霞口温度 |
| multi_stage | 5 | 北海BOD, 威海COD, 威海BOD, 威海硝酸盐, 西霞口多环芳烃 |
| change_point | 1 | 威海多环芳烃 |
| increasing | 0 | - |
| unclear | 0 | - |

**实际用到的类别**：7/8（increasing 未出现，unclear 未出现）

---

## 各置信度数量

| 置信度 | 数量 | 样本 |
|---|---|---|
| high | 9 | 北海温度, 北海盐度, 北海溶解氧, 北海COD, 北海BOD, 威海溶解氧, 威海COD, 威海BOD, 西霞口温度, 西霞口水深 |
| medium | 9 | 西霞口叶绿素, 西霞口硝酸盐, 北海水深, 威海硝酸盐, 威海叶绿素, 威海多环芳烃, 西霞口盐度, 西霞口多环芳烃 |
| low | 0 | - |

---

## 存在歧义的样本

### 1. 北海水深 (monthly-f756e4d7666913e6) - medium
- 9个月无明显趋势，最后2个月下降
- 判为decreasing是否过度？改为stable+末端decrease更准确的担忧
- 当前选择：decreasing

### 2. 威海叶绿素 (monthly-77e7c875fd3b038e) - medium
- 全序列11个月，仅2025-12出现极端高值（~33 μg/L）
- 判为rise_then_fall是否过度？实际只有1个月显著偏离
- 当前选择：rise_then_fall

### 3. 西霞口盐度 (monthly-d183444b225ef8b3) - medium
- 高位平台 + 小幅下跌后再回升 + 末期下降
- 判为rise_then_fall是否忽略了中间的回升？是否需要改multi_stage？
- 当前选择：rise_then_fall（含5个阶段），confidence=medium

### 4. 威海硝酸盐 (monthly-fa17a3df9f1b7ce5) - medium
- 4个阶段，变化幅度较小（1.0→0.28→0.61→0.58）
- 判为multi_stage是否过度拆分？
- 当前选择：multi_stage

### 5. 西霞口多环芳烃 (monthly-7d1c5aec44d70973) - medium
- 前8个月无趋势，后2个月下降
- 判为multi_stage（仅2个阶段）是否合适？
- 当前选择：multi_stage

---

## 标准漂移检查

| 检查项 | 结论 |
|---|---|
| stable定义一致 | ✓ 两个stable样本都用"方向多次反转"判据 |
| decreasing定义一致 | ✓ 两个decreasing都用"无明显反向+持续同向" |
| rise_then_fall/fall_then_rise | ✓ 统一为"单峰/单谷"结构 |
| multi_stage阶段数 | ⚠ 2个阶段至4个阶段不等，边界需确认 |
| change_point定义 | ✓ 按规范限定为结构性突跃 |
| 前期6个样本的新增12个样本比较 | ✓ 同类样本标注方法一致 |

---

## 需要用户复核的样本

1. **monthly-f756e4d7666913e6**（北海水深）： decreasing vs stable?
2. **monthly-77e7c875fd3b038e**（威海叶绿素）：rise_then_fall vs multi_stage?
3. **monthly-d183444b225ef8b3**（西霞口盐度）：rise_then_fall vs multi_stage?
4. **monthly-7d1c5aec44d70973**（西霞口多环芳烃）：multi_stage（仅2段）vs decreasing?

---

## 规范是否需要调整

- `multi_stage` 的最少阶段数：目前有2段也判为multi_stage（西霞口多环芳烃），规范要求"3+"，需要统一
- `rise_then_fall` 的 "单峰"：威海叶绿素的极端单月峰是否该算
- 建议：待用户确认后，可能需要对 `multi_stage` 边界做明确补充
