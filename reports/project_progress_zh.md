# 项目当前进展中文总结

这份文档是给小组内部快速理解项目用的，不是正式论文正文。

## 1. 当前已经完成了哪些阶段

目前项目已经完成了从数据整理到政策规则修正的大部分建模工作：

1. 数据整理和数据质量检查；
2. 调价窗口级建模主表构建；
3. 现行机制复现；
4. 价格传递不对称分析；
5. 社会福利损失函数；
6. 多种调价策略模拟；
7. 福利函数稳健性检验；
8. S5 简化调价规则提取；
9. 按《石油价格管理办法》加入 40/80/130 美元政策区间修正；
10. 中文解释文档整理。

## 2. 每个阶段做了什么

### 数据阶段

把原始 CSV、PDF、PNG 整理到 `data/raw/`，清洗后的数据放到 `data/processed/`。核心结果是 `modeling_dataset.csv`，它把每个调价窗口对应的国际油价、国内调价、CPI/PPI、PMI、原油进口等变量合到一起。

### 机制复现阶段

先用线性模型估计国际油价变化和国内调价幅度的关系，再加入 50 元/吨调价门槛和搁浅累计规则。结论是：加入门槛后，模型更能解释“不调价”窗口。

### 价格传递阶段

计算理论调价到实际调价的传递比例。发现上调和下调存在一定不对称，不同油价区间也存在差异。

### 福利函数阶段

把消费者损失、炼厂损失、CPI 冲击、价格波动、能源安全五类因素合成社会福利损失，用来比较不同调价策略。

### 策略模拟阶段

比较了现实机制 S0、完全传导 S1、固定比例传导 S2、分段平滑 S3/S5 等策略。基础结果显示 S1 数学损失低，但 S5 更适合作为政策建议。

### 稳健性检验阶段

做了联合标准化、raw loss 缩放、权重敏感性、代理油价稳健性。结论是：S5 优于现实机制 S0 的结论比较稳健。

### 政策区间修正阶段

根据《石油价格管理办法》，加入 40 美元地板价、80-130 美元加工利润扣减、130 美元以上不提或少提。这个模型更符合政策条文，尤其改善了低油价区间解释。

## 3. 现在有哪些核心数据文件

- `data/processed/modeling_dataset.csv`：基础建模主表。
- `data/processed/modeling_dataset_mechanism.csv`：加入 raw/rule 机制复现结果。
- `data/processed/modeling_dataset_pass_through.csv`：加入价格传递比例。
- `data/processed/strategy_simulation_results.csv`：S0-S5 策略模拟长表。
- `data/processed/modeling_dataset_policy_band.csv`：加入 40/80/130 政策区间修正。
- `data/processed/policy_constrained_strategy_results.csv`：政策区间约束后的策略模拟结果。

## 4. 现在有哪些核心模型

### 线性机制复现模型

用国际油价窗口变化解释国内调价幅度：

```text
实际调价 ≈ k × 国际油价变化 + b
```

### rule_threshold_carry 模型

在线性理论调价基础上加入 50 元/吨门槛和搁浅累计。

### pass-through 分析模型

计算实际调价占理论调价的比例，用来分析价格传递是否充分。

### 福利损失函数

把五类损失加权求和：消费者、炼厂、CPI、波动、能源安全。

### S5 分段平滑策略

小幅调价充分传导，大幅调价逐步平滑，极端冲击削峰。

### policy_band 模型

加入 40/80/130 美元政策区间，增强与管理办法的一致性。

## 5. 当前主要结论

1. Brent-WTI 加权油价是较好的主代理变量，Brent-WTI 平均值也可做稳健性对照。
2. 50 元门槛和搁浅累计能明显改善不调价窗口识别。
3. 低油价区间误差最大，引入 40 美元地板价后低油价误差下降。
4. 原福利函数下 S1/S4 数学损失最低，但 S5 更适合作为政策建议。
5. 联合标准化和 raw loss 检验说明：S5 优于现实机制 S0 的结论比较稳健。
6. 政策区间约束后，S1 总损失最低，但 S5/S6 调价更平滑、政策接受性更好。

## 6. 目前模型还存在什么问题

- 加工成本、税金、流通费用和利润没有真实数据，只是通过政策区间做近似。
- 福利损失函数是简化版，权重有主观性。
- 130 美元以上极端高油价样本没有出现，所以该区间规则缺少实证检验。
- S6 的 CPI 封顶约束在当前样本中没有额外触发。
- 中文报告和图表说明已经补齐，但论文正文还需要进一步组织语言。

## 7. 下一步应该做什么

可以开始论文整合。建议顺序：

1. 写数据来源和数据预处理；
2. 写机制复现，包括 raw、rule、policy_band；
3. 写价格传递不对称和油价区间分析；
4. 写福利损失函数和策略模拟；
5. 写稳健性检验；
6. 最后写政策建议：推荐“政策区间修正 + S5 分段平滑传导”。

## 8. 三个队员可以如何分工

### 队员 A：数据和机制复现

负责写数据来源、数据质量、建模主表、raw/rule/policy_band 机制复现。

重点文件：

- `data/data_dictionary.md`
- `reports/data_quality_report_zh.md`
- `outputs/tables/mechanism_rule_validation.csv`
- `outputs/tables/policy_band_mechanism_validation.csv`

### 队员 B：福利函数和策略模拟

负责写福利损失函数、S0-S6 策略设计、策略比较、权重敏感性。

重点文件：

- `reports/welfare_strategy_analysis.md`
- `reports/welfare_robustness_and_policy_rule.md`
- `outputs/tables/welfare_strategy_comparison.csv`
- `outputs/tables/policy_constrained_strategy_comparison.csv`

### 队员 C：图表、稳健性和论文整合

负责整理图表、写稳健性检验、统一论文格式和结论。

重点文件：

- `outputs/figures/figure_explanations_zh.md`
- `outputs/tables/table_explanations_zh.md`
- `outputs/tables/proxy_robustness_strategy_ranking.csv`
- `outputs/tables/simplified_policy_rule.csv`

## 9. 最终论文主线建议

一句话主线：

> 本文先复现我国成品油价格调控机制，再构建社会福利损失函数比较多种调价策略，最终提出符合 40/80/130 美元政策区间、兼顾成本传导和价格平稳的分段调价规则。

