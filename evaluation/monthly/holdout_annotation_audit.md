# Holdout 9样本盲标审计报告

## 完成情况
- 完成样本数：**9/9**
- 规范版本：**annotation_guideline_v1.md**（冻结）
- 标注日期：2026-07-17
- 状态：结果已锁定

---

## 各primary_pattern数量

| 类别 | 数量 | 样本 |
|---|---|---|
| stable | 0 | - |
| decreasing | 0 | - |
| rise_then_fall | 0 | - |
| fall_then_rise | 2 | 威海温度, 威海盐度 |
| multi_stage | 6 | 北海硝酸盐, 北海叶绿素, 北海多环芳烃, 威海水深, 西霞口COD, 西霞口BOD |
| change_point | 1 | 西霞口溶解氧 |
| increasing | 0 | - |
| unclear | 0 | - |

**实际用到的类别**：3/8（multi_stage占主导）

---

## 各置信度数量

| 置信度 | 数量 | 样本 |
|---|---|---|
| high | 6 | 北海硝酸盐, 威海水深, 威海温度, 西霞口溶解氧, 西霞口COD, 西霞口BOD |
| medium | 3 | 北海叶绿素, 北海多环芳烃, 威海盐度 |
| low | 0 | - |

---

## 存在歧义的样本

### 1. 北海叶绿素 (monthly-f8ff2388b939ef47) - medium
- 2026-03月出现极端高值19.18 μg/L，类似威海叶绿素的异常模式
- 判为multi_stage可能过度拆分，但不使用change_point（因为跃迁不持续）
- 记录：极端单月高值模式在新数据中再次出现，确认不修改规范

### 2. 北海多环芳烃 (monthly-dafe790b4dd571a1) - medium
- 前期下降→稳低位→上升→下降，4个阶段
- 整体是multi_stage，是否可以简化为rise_then_fall（将前段下降视为初始）
- 当前选择：multi_stage

### 3. 威海盐度 (monthly-5171fa30c8657984) - medium
- 谷值在2025-11，2026-01起进入平台期
- 是否应作为fall_then_rise但带plateau？是否需要单独标"stable"段？
- 当前选择：fall_then_rise + stable子阶段

---

## 新出现但未修改规范的情况

- **极端单月异常值**（北海叶绿素2026-03=19.18、威海叶绿素已在development中处理过）：在holdout中再次出现
  - 决策：按现有规范判multi_stage，不修改规范
  - 原因：极端值虽明显但不符合"水平跃迁前后维持不同状态"的change_point定义

- **fall_then_rise带平台期**（威海盐度）：fall_then_rise + stable子阶段
  - 决策：可纳入规范但暂不修改
  - 原因：现有规范中stable作为子阶段已允许，无需新增

---

## 标准漂移检查

| 检查项 | 结论 |
|---|---|
| 与development标注方法一致 | ✓ 边界判断（multi_stage、change_point、fall_then_rise）一致 |
| 规范未修改 | ✓ 全部按v1执行 |
| 不参考development算法结果 | ✓ 独立标注 |
| 不读取baseline | ✓ |

---

## 规范是否需要调整

- **无修改建议**。holdout出现的所有模式在现有规范内均能覆盖
- multi_stage过度拆分的边界问题已在development审计中提出
- 北海叶绿素和威海叶绿素的极端高值现象：建议在最终报告中说明，但**不**在标注阶段修改规范

---

## 锁定状态

- 锁定副本：holdout_blind_annotation_locked.xlsx
- 锁定时间：2026-07-17
- 锁定原则：不得因后续看到baseline而修改human字段
