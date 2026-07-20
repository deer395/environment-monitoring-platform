# 月际报告解读标注规范 v1 (修正版)

> 本文档基于首次6个development样本盲标建立，经审核修正后冻存为此版。
> 剩余12个development和全部holdout均以此版为准。
> 时间序列：2025-08 ~ 2026-06（11个月数据点）。

---

## 一、human_primary_pattern 分类操作定义

| 类别 | 操作定义 | 典型形态 |
|---|---|---|
| **stable** | 月均值围绕相近中心水平波动，没有持续单向变化或明显水平跃迁。月际方向频繁反转而非连续同向 | 叶绿素、稳定的化学指标 |
| **increasing** | 主要方向为上升，期间没有足以改变总体结构的重要反向阶段 | 持续上升的水温、藻类等 |
| **decreasing** | 主要方向为下降，期间没有足以改变总体结构的重要反向阶段 | 持续下降的营养盐、污染物 |
| **rise_then_fall** | 存在一个清晰主峰（单一最大月），峰前总体上升，峰后总体下降 | 季节性水温、溶解氧（冬高夏低型） |
| **fall_then_rise** | 存在一个清晰主谷（单一最小月），谷前总体下降，谷后总体上升 | 季节性水温（夏高冬低型） |
| **multi_stage** | 存在三个或以上具有实际意义的方向变化阶段，无法合理压缩为单一上升、下降或一次转折 | 复杂多阶段：升→降→升→稳 |
| **change_point** | 存在一次明显水平跃迁（1-2个月内水平跳变），跃迁前后分别维持在明显不同的水平 | 突变事件：低位稳→高位稳 |
| **unclear** | 图件不足以支持稳定分类，或多个分类同样合理 | 噪声过大、规律不明显 |

**重要说明：月标准差表示月内数据离散程度，不是月平均值的置信区间。stable应依据月均序列是否缺乏持续方向、明显转折或水平跃迁判断，不能以"月际变化落在月标准差内"作为判据。**

---

## 二、human_trend_direction 分类规则

| primary_pattern | trend_direction | 备注 |
|---|---|---|
| stable | stable | 必须一致 |
| increasing | increase | 必须一致 |
| decreasing | decrease | 必须一致 |
| rise_then_fall | mixed | 一般映射 |
| fall_then_rise | mixed | 一般映射 |
| multi_stage | mixed | 一般映射 |
| change_point | increase / decrease / mixed | 根据前后水平判断 |
| unclear | unclear | 必须一致 |

---

## 三、human_key_stages 阶段划分规则

### 3.1 格式
```
YYYY-MM~YYYY-MM: direction_or_state;
YYYY-MM~YYYY-MM: direction_or_state
```

### 3.2 允许的方向/状态词
- `increase` - 上升
- `decrease` - 下降
- `stable` - 稳定
- `high_level` - 高位平稳
- `low_level` - 低位平稳
- `short_rise` - 短暂回升
- `short_fall` - 短暂回落
- `abrupt_increase` - 突然上升
- `abrupt_decrease` - 突然下降

### 3.3 合并规则
- 相邻同方向月份合并，但不同速率可作为不同阶段
- 轻微反向不单独建阶段（除非影响对主要过程的理解）
- 阶段边界使用实际发生方向改变的月份
- 允许阶段首尾共享转折月份（需全表统一）

### 3.4 速率变化规则
连续缓慢下降后转为快速下降，仍可视为同一下降主趋势。是否拆分阶段取决于报告是否需要表达速率变化，但不应因此将总体模式改为multi_stage。

### 3.5 边界月份选择
- 阶段A: `2025-08~2025-09: stable` (2个月)
- 阶段B: `2025-09~2026-02: decrease` (6个月，2025-09 共享)
- 含义：2025-09 同时作为上一阶段结束和下一阶段开始

---

## 四、human_change_point 规则

### 4.1 change_point_present
- `yes`：存在主要方向改变或明显水平跃迁
- `no`：无，或仅有小幅波动
- `unclear`：无法稳定判断

### 4.2 change_point_month
- 仅在 present=yes 时填写
- 填写最主要转折发生的月份
- 若存在多个重要转折，只写最主要的一个，其他写入 key_stages

### 4.3 与 multi_stage 的区别
- change_point：单次水平跃迁，跃迁前后各自稳定
- multi_stage：多次方向变化或3+个有意义的阶段

---

## 五、human_should_describe_short_reversal 规则

短暂反向是嵌在明确主趋势中的短期反向变化（通常1-2个时间间隔），之后必须重新恢复原主趋势。其显著性应结合相邻月变化尺度和整体序列判断，不使用所有变量通用的固定百分比。

- `yes`：存在明确主趋势，中间出现明显反向变化后恢复原主趋势，且反向幅度明显高于相邻月份的常规波动
- `no`：不存在上述模式，或反向变化本身是多阶段中的正常阶段
- `unclear`：无法稳定判断

**判定关键**：如果"反向"之后没有恢复原趋势，则它不是短暂反向，而是多阶段中的正常阶段。不要使用固定百分比阈值（如30%），因为不同变量的量纲和基准值差异很大。

---

## 六、human_highest/lowest/max_std_month 规则

- 必须直接依据图件（即数据点位置）确定
- 不得凭目测无法区分时强行选择
- 难以区分时，降低 confidence 并在 reference_summary 中说明

---

## 七、human_reference_summary 写作要求

- 1-3 句话
- 覆盖主要月际路径（不逐月罗列）
- 包含最重要阶段和转折
- 可包含最高月、最低月、最大标准差月份
- 不解释成因
- 不使用"导致、驱动、受……影响"等词
- 不添加图中不存在的事实
- 不要求与旧算法句式一致

---

## 八、容易混淆类型的区分方法

### 8.1 stable vs decreasing
- stable：围绕中心水平波动，方向频繁反转，没有持续同方向变化
- decreasing：存在连续多个月的持续下降（即使缓慢），几乎没有反弹
- 关键：看是否连续多个月同方向变化 + 有无反弹
- 示例：西霞口叶绿素 2.07-2.89（月际反复波动）→ stable；西霞口硝酸盐 0.89→0.26（连续下行）→ decreasing

### 8.2 decreasing vs multi_stage
- decreasing：总体单调向下，期间存在的速率变化可以拆分但方向相同
- multi_stage：存在反向变化（如降→升），或存在3个以上方向不同的阶段
- 关键：看是否有任何反向运动
- 示例：西霞口硝酸盐 0.89→0.26 全程向下无反弹 → decreasing；北海BOD 升→降→升→稳 → multi_stage

### 8.3 change_point vs 平滑趋势
- change_point：1-2个月内水平跳变，跃迁后稳定
- 平滑趋势（increase/decrease/multi_stage）：多个月连续变化，没有明显水平切换
- 关键：变化是"突变"还是"渐变"
- 示例：威海多环芳烃 2.65→8.50（1个月跳变）→ change_point；北海温度 25→2（4个月）→ fall_then_rise

### 8.4 rise_then_fall vs multi_stage
- rise_then_fall：单个清晰主峰，峰前升峰后降
- multi_stage：多峰或峰后还有更复杂变化
- 关键：峰的个数和峰后是否继续复杂

---

## 九、6个development样本审核修正记录

| 样本 | 初次 | 审核后 | 修改点 |
|---|---|---|---|
| monthly-d12f3a52c8bedd0b (西霞口叶绿素) | stable, high | stable, **medium** | 降confidence，修正stable理由 |
| monthly-dcdc992a3c1facfd (北海温度) | fall_then_rise | fall_then_rise | 删除前2月stable子阶段 |
| monthly-d43b8b6caf84505d (北海溶解氧) | rise_then_fall | rise_then_fall | 无修改 |
| monthly-9c9c7f6877db1fe8 (西霞口硝酸盐) | decreasing (首段stable) | decreasing (首段decrease), **medium** | 首段改decrease，降confidence |
| monthly-0c082b1ada4cbf02 (北海BOD) | multi_stage, short_rev=yes | multi_stage, **short_rev=no** | 短暂反向改为no |
| monthly-def4dd53323e22af (威海多环芳烃) | change_point | change_point | 拆分前期下降段 |

---

_本规范由6个development样本盲标生成，经审核修正后冻存为v1。_
_不得将holdout样本的观察结果反向注入本规范。_
