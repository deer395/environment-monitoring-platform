# 月际报告解读标注规范（草稿 v0）

> 本文档记录从首次6个development样本盲标中提取的标注规则。
> 适用于：D:\海洋牧场\海洋牧场\evaluation\monthly\figures\blind\ 下的所有月均变化图。
> 时间序列：2025-08 ~ 2026-06（11个月数据点）。

---

## 一、human_primary_pattern 分类操作定义

| 类别 | 操作定义 | 典型形态 |
|---|---|---|
| **stable** | 11个点都围绕相近水平变化，month-to-month变化在月标准差范围内，**没有清晰持续方向** | 叶绿素、稳定的化学指标 |
| **increasing** | 主要方向为上升，期间**没有足以改变总体结构的重要反向阶段**；允许中间存在小幅波动 | 持续上升的水温、藻类等 |
| **decreasing** | 主要方向为下降，期间**没有足以改变总体结构的重要反向阶段**；允许中间存在小幅波动 | 持续下降的营养盐、污染物 |
| **rise_then_fall** | 存在**一个清晰主峰**（单一最大月），峰前总体上升，峰后总体下降 | 季节性水温、溶解氧（冬高夏低型） |
| **fall_then_rise** | 存在**一个清晰主谷**（单一最小月），谷前总体下降，谷后总体上升 | 季节性水温（夏高冬低型） |
| **multi_stage** | 存在**三个或以上具有实际意义的阶段**，无法合理压缩为单一上升、下降或一次转折 | 复杂多阶段：升→降→升→稳 |
| **change_point** | 存在**一次明显水平跃迁**（1-2个月内水平跳变），跃迁前后分别维持在明显不同的水平 | 突变事件：低位稳→高位稳 |
| **unclear** | 图件不足以支持稳定分类，或多个分类同样合理 | 噪声过大、规律不明显 |

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

**注意**：human_trend_direction 的可选值是 `increase, decrease, stable, mixed, unclear`（不带 `_ing` 后缀），与 pattern 的命名形式不同。`decreasing` (pattern) 对应 `decrease` (trend)，二者含义相同。

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
- **相邻同方向月份合并**（不为每个月单独建一个阶段）
- **轻微反向不单独建阶段**（除非影响对主要过程的理解）
- **阶段边界使用实际发生方向改变的月份**
- **允许阶段首尾共享转折月份**（需全表统一）

### 3.4 边界月份选择
- 阶段A: `2025-08~2025-09: stable` (2个月)
- 阶段B: `2025-09~2026-02: decrease` (6个月，2025-09 共享)
- 含义：2025-09 月同时作为上一阶段结束和下一阶段开始

---

## 四、human_change_point 规则

### 4.1 change_point_present
- `yes`：存在**主要方向改变**或**明显水平跃迁**
- `no`：无，或仅有小幅波动
- `unclear`：无法稳定判断

### 4.2 change_point_month
- 仅在 present=yes 时填写
- 填写**最主要转折发生的月份**
- 若存在多个重要转折，**只写最主要的一个**，其他写入 key_stages

### 4.3 与 multi_stage 的区别
- change_point：**单次**水平跃迁，跃迁前后各自稳定
- multi_stage：**多次**方向变化或**3+个**有意义的阶段

---

## 五、human_should_describe_short_reversal 规则

- `yes`：短暂反向变化**明显**（幅度显著、持续2个月以上），且**会影响对主要过程的理解**
- `no`：幅度较小，或只属于普通月际噪声，或无法从图中明显识别
- `unclear`：无法稳定判断

**判断阈值**：
- 幅度：变化 ≥ 30% 的当月均值
- 持续：≥ 2 个月
- 例：BOD 的 2026-02→2026-04 短暂回升（1.19→2.15，+81%），属 yes

---

## 六、human_highest/lowest/max_std_month 规则

- 必须**直接依据图件**（即数据点位置）确定
- 不得凭目测**无法区分**时强行选择
- 难以区分时，**降低 confidence** 并在 reference_summary 中说明
- 同一月份可能同时是 highest 和 max_std_month（不冲突）

---

## 七、human_reference_summary 写作要求

- 1-3 句话
- 覆盖**主要月际路径**（不逐月罗列）
- 包含**最重要阶段和转折**
- 可包含最高月、最低月、最大标准差月份
- **不解释成因**
- **不使用**"导致、驱动、受……影响"等词
- **不添加图中不存在的事实**
- 不要求与旧算法句式一致

---

## 八、容易混淆类型的区分方法

### 8.1 stable vs decreasing
- stable：所有点都围绕相近水平，**没有清晰持续方向**，变化在月标准差内
- decreasing：尽管有波动，但**整体向下**移动超过月标准差
- 关键：先看每个月的变化是否都在误差棒内。如果是 → stable
- 示例：西霞口叶绿素 2.07-2.89 → stable；西霞口硝酸盐 0.89→0.26 → decreasing

### 8.2 decreasing vs multi_stage
- decreasing：**总体单调向下**，期间存在的"稳定段"是减速段，不构成新方向
- multi_stage：存在**反向变化**（如降→升），或存在**3个以上不同速率段**
- 关键：看是否有任何**反向运动**
- 示例：西霞口硝酸盐 0.89→0.26 全程向下无反弹 → decreasing；北海BOD 升→降→升→稳 → multi_stage

### 8.3 change_point vs 平滑趋势
- change_point：**1-2个月内水平跳变** ≥ 2-3 倍月标准差，跃迁后稳定
- 平滑趋势（increase/decrease/multi_stage）：**多个月连续变化**，没有明显的水平切换
- 关键：变化是"突变"还是"渐变"
- 示例：威海多环芳烃 2.65→8.50（1个月跳变）→ change_point；北海温度 25→2（4个月）→ fall_then_rise

### 8.4 rise_then_fall vs multi_stage
- rise_then_fall：**单个清晰主峰**，峰前升峰后降
- multi_stage：**多峰**或峰后还有更复杂变化
- 关键：峰的个数和峰后是否继续复杂
- 示例：北海溶解氧 单峰 → rise_then_fall；北海BOD 主峰+回升 → multi_stage

---

## 九、本轮6个样本中发现的歧义

### 9.1 西霞口叶绿素（stable）
- 争议：波动范围 2.07-2.89（约30% spread）是否"稳定"
- 判定：按月标准差（约 0.5-2.1）评估，月际变化均在误差棒内
- 当前选择：**stable**

### 9.2 北海温度（fall_then_rise）前2个月stable
- 争议：1个变化（25.22→25.09）是否值得单列stable阶段
- 判定：差异0.13，在月标准差~0.5内，确实稳定
- 当前选择：**保留 stable 子阶段**

### 9.3 西霞口硝酸盐（decreasing）首段
- 争议：前6个月从0.89缓慢降至0.75（16%），是否属stable
- 判定：月际差异均在月标准差内（0.15-0.26），可视作稳定
- 当前选择：**保留 stable 子阶段，整体 decreasing**

### 9.4 北海BOD 短暂回升
- 争议：2026-02→2026-04 短暂回升（1.19→2.15，+81%）算"显著短暂反向"还是噪声
- 判定：幅度+81%、持续2个月、明显
- 当前选择：**should_describe_short_reversal=yes**

### 9.5 威海多环芳烃 首点2025-08
- 争议：2025-08（3.97）高于其他低水平月（1.08-2.65），是否应单独标"开始下降"
- 判定：2025-08→2025-09 从3.97降至2.06（-48%），确实有下降
- 当前选择：**保留为 stable (low level) 的一部分**，2025-08视为初始水平

---

## 十、对6个样本是否需要回改的结论

| 样本 | 初次标签 | 复核后 | 是否修改 |
|---|---|---|---|
| monthly-d12f3a52c8bedd0b (西霞口叶绿素) | stable | stable | 否 |
| monthly-dcdc992a3c1facfd (北海温度) | fall_then_rise | fall_then_rise | 否 |
| monthly-d43b8b6caf84505d (北海溶解氧) | rise_then_fall | rise_then_fall | 否 |
| monthly-9c9c7f6877db1fe8 (西霞口硝酸盐) | decreasing | decreasing | 否 |
| monthly-0c082b1ada4cbf02 (北海BOD) | multi_stage | multi_stage | 否 |
| monthly-def4dd53323e22af (威海多环芳烃) | change_point | change_point | 否 |

**结论**：6个样本初次标注与复核后一致，**无需回改**。所有标签 confidence=high。

---

## 十一、待用户确认的关键问题

1. **stable的边界**：波动范围30%是否算"稳定"？还是仅当月际差异都在月标准差内才算？
2. **slow decrease vs stable**：西霞口硝酸盐首段（16%/6月）当前判stable，是否合适？
3. **短暂回升的阈值**：1.19→2.15（+81%，2个月）算yes，是否需要更明确的阈值标准？
4. **change_point首点处理**：威海多环芳烃2025-08（3.97）高于后续低水平段（1.08-2.65），是否应在key_stages中加"decrease"阶段？
5. **北海温度前2个月stable子阶段**：25.22→25.09（差异0.13）是否值得单列？
