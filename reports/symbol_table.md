# 符号说明表

本符号表用于“任务一：机制理解与历史数据验证”阶段，统一数学符号、代码字段、单位和用途。

| 符号 | 对应代码字段 | 中文含义 | 单位 | 用途 |
| --- | --- | --- | --- | --- |
| `t` | 调价窗口排序索引 | 调价窗口编号 | 无 | 按调价执行日期或公告日期排序后的窗口序号 |
| `O_t` | `brent_wti_weighted_window_avg` | 国际油价窗口均值，主口径为 Brent/WTI 加权均值 | 美元/桶 | 表示调价窗口前最近 10 个有效交易日的国际油价水平 |
| `ΔO_t` | `brent_wti_weighted_window_change` | 国际油价窗口变化 | 美元/桶 | 相对上一调价窗口的国际油价窗口均值变化，是机制复现主解释变量 |
| `P_t` | `avg_ceiling_after_cny_per_ton` | 国内成品油平均最高限价 | 元/吨 | 北京汽油、柴油最高限价的平均值，用于刻画国内价格水平 |
| `ΔP_actual_t` | `avg_adjust_cny_per_ton` | 实际平均调价幅度 | 元/吨 | 汽油、柴油调价幅度的平均值，是机制复现的被解释变量 |
| `ΔP_raw_t` | `theory_adjust_raw_cny_per_ton` | 线性模型估计的原始理论调价幅度 | 元/吨 | 使用上一阶段基线回归系数 `k`、`b` 直接计算的理论调价 |
| `ΔP_rule_t` | `theory_adjust_rule_cny_per_ton` | 加入政策规则后的理论调价幅度 | 元/吨 | 在 `ΔP_raw_t` 基础上加入 50 元/吨门槛和搁浅累计规则后的理论调价 |
| `A_t` | `carry_before_decision_cny_per_ton`、`carry_after_decision_cny_per_ton` | 累计未调价幅度/搁浅累计项 | 元/吨 | 表示未达到 50 元/吨门槛时保留到后续窗口的累计理论调价 |
| `e_t` | `theory_error_rule_cny_per_ton` 或 `theory_error_raw_cny_per_ton` | 理论调价误差 | 元/吨 | 实际平均调价幅度减理论调价幅度，用于衡量机制复现偏差 |
| `r_t` | `pass_through_ratio` | 价格传递比例 | 无 | `avg_adjust_cny_per_ton / theory_adjust_rule_cny_per_ton`，用于分析理论调价向实际调价的传递程度 |
| `CPI_t` | `cpi_yoy_pct` | 居民消费价格指数同比 | % | 宏观价格环境变量 |
| `PPI_t` | `ppi_yoy_pct` | 工业生产者出厂价格指数同比 | % | 工业价格环境变量 |
| `PMI_t` | `nbs_manufacturing_pmi`、`non_manufacturing_pmi`、`nbs_general_pmi` | 采购经理指数 | 指数点 | 经济景气度变量，用于解释调价偏差或传递差异 |

主样本区间设为 `2016-01-01` 至 `2026-05-09`。`2013-2015` 年数据保留在基础主表中，后续可作为机制过渡期或稳健性补充样本。
