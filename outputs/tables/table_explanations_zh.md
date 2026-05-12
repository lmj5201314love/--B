# outputs/tables 结果表中文说明索引

本文件用于解释 `outputs/tables/` 下的重要 CSV 表格。字段名仍保留英文，方便脚本继续运行。

## data_quality_summary.csv

### 这个表是干什么的？
汇总所有原始 CSV 的数据质量情况。

### 主要字段解释
- `file`：文件名。
- `row_count`、`column_count`：行数和列数。
- `date_min`、`date_max`：日期范围。
- `missing_counts_json`：每列缺失值数量。
- `anomaly_hints`：异常值提示。

### 应该怎么看？
重点看日期范围是否覆盖研究期、缺失值是否多、异常提示是否影响模型。

### 当前结论
- 核心油价和调价公告数据较完整。
- 原油进口均价存在异常月份。
- PMI 综合指数存在较多缺失。

### 论文中可以放在哪里？
数据预处理和数据质量说明部分。

## oil_price_daily_summary.csv

### 这个表是干什么的？
说明合并后的国际油价日度数据质量。

### 主要字段解释
- `series`：油价序列。
- `non_missing_count`：非缺失数量。
- `date_min`、`date_max`：覆盖时间范围。
- `mean`、`min`、`max`：基本统计量。

### 应该怎么看？
重点看 Brent、WTI、basket 的日期范围和极端值。

### 当前结论
- Brent/WTI 覆盖时间较长。
- WTI 的最低值为负，反映 2020 年极端负油价事件。

### 论文中可以放在哪里？
国际油价数据说明部分。

## fuel_adjustment_summary.csv

### 这个表是干什么的？
统计国内成品油调价窗口的上调、下调和不调价次数。

### 主要字段解释
- `total_windows`：调价窗口总数。
- `up_count`、`down_count`、`no_adjust_count`：上调、下调、不调价次数。
- `average_up_adjust_cny_per_ton`：平均上调幅度。
- `average_down_adjust_cny_per_ton`：平均下调幅度。

### 应该怎么看？
看调价次数结构和平均调价幅度。

### 当前结论
- 调价窗口中既有上调也有下调，还有较多不调价窗口。
- 下调平均幅度绝对值略大于上调平均幅度。

### 论文中可以放在哪里？
数据描述性统计部分。

## modeling_dataset_quality.csv

### 这个表是干什么的？
检查建模主表每个字段的缺失和数值范围。

### 主要字段解释
- `missing_count`：缺失数量。
- `numeric_min`、`numeric_mean`、`numeric_max`：数值范围。

### 应该怎么看？
重点看宏观变量和进口变量是否缺失。

### 当前结论
- 核心调价和油价窗口变量完整。
- 原油进口变量后期有缺失，因为原始数据只到 2024-12。

### 论文中可以放在哪里？
建模主表构建说明部分。

## mechanism_baseline_comparison.csv

### 这个表是干什么的？
比较不同国际油价代理变量对实际调价幅度的简单线性拟合效果。

### 主要字段解释
- `proxy_variable`：油价代理变量。
- `k`、`b`：线性模型系数。
- `MAE`、`RMSE`：误差指标。
- `direction_accuracy`：方向准确率。

### 应该怎么看？
误差越低、方向准确率越高，代理变量越合适。

### 当前结论
- `brent_wti_weighted_window_change` 的 RMSE 最低。
- `brent_wti_avg_window_change` 的 MAE 和方向准确率略有优势，可做稳健性对照。

### 论文中可以放在哪里？
机制复现基线模型部分。

## mechanism_rule_validation.csv

### 这个表是干什么的？
比较 raw 线性模型和加入 50 元门槛、搁浅累计后的 rule 模型。

### 主要字段解释
- `model`：模型类型。
- `direction_accuracy`：上调/下调/不调价方向是否判断正确。
- `adjustment_accuracy`：是否调价判断正确率。
- `no_adjust_recognition_accuracy`：不调价识别准确率。

### 应该怎么看？
重点看 rule 模型是否提高不调价识别。

### 当前结论
- rule 模型显著提高方向准确率和不调价识别。
- raw 模型在实际调价窗口的幅度拟合略好。

### 论文中可以放在哪里？
现行机制复现部分。

## pass_through_asymmetry.csv

### 这个表是干什么的？
分析价格传递是否存在上调、下调不对称。

### 主要字段解释
- `mean_pass_through_ratio`：平均传递比例。
- `mean_pass_through_gap`：理论调价和实际调价差距。
- `under_transmitted_rate`：不足传递比例。
- `over_transmitted_rate`：过度传递比例。

### 应该怎么看？
比较理论上调和理论下调窗口的传递比例差异。

### 当前结论
- 存在一定传递不对称。
- 实际下调窗口的传递比例反而更高，说明样本中未表现出简单的“下调滞后”。

### 论文中可以放在哪里？
价格传递不对称分析部分。

## oil_price_regime_analysis.csv

### 这个表是干什么的？
按低油价、正常油价、高油价区间比较误差和传递情况。

### 主要字段解释
- `oil_price_regime`：油价区间。
- `mean_abs_error`：平均绝对误差。
- `no_adjust_rate`：不调价比例。

### 应该怎么看？
看哪个油价区间误差最大。

### 当前结论
- 低油价区间误差最大，不调价比例最高。
- 这为后续引入 40 美元地板价提供依据。

### 论文中可以放在哪里？
油价区间调控分析部分。

## welfare_strategy_comparison.csv

### 这个表是干什么的？
比较 S0-S5 策略在基础福利函数下的总福利损失。

### 主要字段解释
- `strategy`：策略名称。
- `total_loss_sum`：总福利损失。
- `consumer_loss_sum` 等：分项福利损失。
- `final_cumulative_unmet_gap`：最终累计未传导缺口。

### 应该怎么看？
总损失越低，策略在当前福利函数下越好。

### 当前结论
- S1/S4 在原内部标准化口径下总损失最低。
- S5 优于现实机制 S0，更适合作为政策建议候选。

### 论文中可以放在哪里？
福利损失函数和策略比较部分。

## welfare_sensitivity_ranking.csv

### 这个表是干什么的？
在不同福利权重情景下重新比较策略排名。

### 主要字段解释
- `weight_scenario`：权重情景。
- `rank`：排名。
- `best_fixed_lambda`、`best_lambda_*`：最优传导比例。

### 应该怎么看？
看 S5 或 S1 的排名是否随权重改变。

### 当前结论
- S1/S4/S5/S0 的相对排名较稳定。
- S5 的推荐分段参数也较稳定。

### 论文中可以放在哪里？
权重敏感性分析部分。

## welfare_strategy_comparison_joint_norm.csv

### 这个表是干什么的？
使用全策略联合标准化后重新比较福利损失。

### 主要字段解释
- `rank`：联合标准化下策略排名。
- `total_loss_sum`：联合标准化后的总损失。

### 应该怎么看？
比较它和 `welfare_strategy_comparison.csv` 的排名是否变化。

### 当前结论
- S5 排名升至第 1。
- 说明“完全传导数学最优”对标准化口径敏感。

### 论文中可以放在哪里？
福利函数稳健性检验部分。

## welfare_strategy_comparison_raw_scaled.csv

### 这个表是干什么的？
不用 min-max 标准化，直接对 raw loss 做固定尺度缩放后比较策略。

### 主要字段解释
- `total_loss_sum`：raw loss 缩放后的总损失。
- `rank`：策略排名。

### 应该怎么看？
看平滑策略是否仍优于现实机制。

### 当前结论
- S2 排名第 1，但累计未传导缺口较大。
- S5 排名第 2，并仍优于 S0。

### 论文中可以放在哪里？
福利函数稳健性检验部分。

## policy_constraint_comparison.csv

### 这个表是干什么的？
比较各策略的政策可接受性。

### 主要字段解释
- `large_up_count`：上调幅度大于等于 300 的次数。
- `extreme_up_count`：上调幅度大于等于 800 的次数。
- `policy_acceptability_score`：政策可接受性分数，越低越好。

### 应该怎么看？
不要只看福利损失，也要看大幅上调和波动是否过大。

### 当前结论
- S1/S4 虽然损失低，但政策可接受性较差。
- S5 比 S1/S0 更均衡。

### 论文中可以放在哪里？
政策可执行性约束分析部分。

## simplified_policy_rule.csv

### 这个表是干什么的？
把 S5 策略提炼成论文可写的简化调价规则。

### 主要字段解释
- `theory_adjust_abs_range`：理论调价绝对幅度区间。
- `recommended_lambda`：建议传导比例。
- `policy_meaning`：政策含义。

### 应该怎么看？
直接看每个理论调价区间对应的传导比例。

### 当前结论
- 小幅波动接近充分传导。
- 大幅和极端波动要平滑削峰。

### 论文中可以放在哪里？
最终政策建议部分。

## proxy_robustness_strategy_ranking.csv

### 这个表是干什么的？
换不同国际油价代理变量后，重新计算机制复现和策略表现。

### 主要字段解释
- `proxy_variable`：油价代理。
- `mechanism_MAE`、`mechanism_RMSE`：机制复现误差。
- `S5_vs_S0_improvement_pct`：S5 相对现实机制的改善比例。

### 应该怎么看？
看 S5 是否在所有代理下都优于 S0。

### 当前结论
- 五种代理下 S5 均优于 S0。
- 主结论不依赖单一油价代理。

### 论文中可以放在哪里？
代理变量稳健性检验部分。

## policy_band_mechanism_validation.csv

### 这个表是干什么的？
比较 raw、原 rule、政策区间修正 policy_band_rule 三个机制复现模型。

### 主要字段解释
- `low_oil_MAE`：低油价区间误差。
- `normal_oil_MAE`：正常油价区间误差。
- `high_oil_MAE`：高油价区间误差。
- `low_oil_no_adjust_recognition_accuracy`：低油价不调价识别率。

### 应该怎么看？
重点看 policy_band 是否改善低油价区间。

### 当前结论
- policy_band 降低低油价 MAE。
- policy_band 提高不调价识别。
- 整体 MAE 略变差，属于政策一致性修正带来的代价。

### 论文中可以放在哪里？
政策区间修正模型部分。

## policy_constrained_strategy_comparison.csv

### 这个表是干什么的？
在 40/80/130 美元政策区间约束后，重新比较 S0、S1、S5、S6 策略。

### 主要字段解释
- `total_loss_sum`：总福利损失。
- `large_up_count`、`extreme_up_count`：大幅和极端上调次数。
- `final_cumulative_unmet_gap`：累计未传导缺口。

### 应该怎么看？
同时看总损失和大幅上调次数。

### 当前结论
- 政策区间下 S1 总损失最低。
- S5/S6 上调更平滑，但累计缺口更高。
- 当前样本中 S6 与 S5 一致，说明额外封顶约束没有触发。

### 论文中可以放在哪里？
政策约束下策略模拟部分。
