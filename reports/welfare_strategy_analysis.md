# 社会福利损失函数与调价策略模拟报告

## 1. 本阶段完成内容

本阶段进入“任务二”的基础版：社会福利损失函数与多策略比较。没有使用强化学习、复杂动态规划或策略优化，只构建可解释、可落地的窗口级策略模拟框架。

主要完成：

- 扩展 `reports/symbol_table.md`，加入福利损失与策略模拟符号；
- 新增 `src/welfare_loss.py`，实现五类福利损失分项、标准化与加权总损失；
- 新增 `scripts/09_welfare_strategy_simulation.py`，模拟 S0 到 S5 六类策略；
- 新增 `scripts/10_welfare_sensitivity.py`，在五组权重情景下重新计算策略排名；
- 输出策略模拟长表、策略比较表、敏感性排名表和四类福利策略图表。

## 2. 福利损失函数定义

对每个调价窗口 `t`，设策略实际调价幅度为 `a_t`，理论调价幅度为 `theory_adjust_rule_cny_per_ton`。五类 raw loss 定义如下：

```text
consumer_loss_raw = max(a_t, 0)^2
refinery_loss_raw = (theory_adjust - a_t)^2
cpi_loss_raw = max(a_t, 0)^2 * cpi_pressure_factor
volatility_loss_raw = (a_t - a_{t-1})^2
unmet_gap = theory_adjust - a_t
cumulative_unmet_gap = sum(unmet_gap)
security_loss_raw = cumulative_unmet_gap^2
```

其中：

```text
cpi_pressure_factor = 1 + max(cpi_yoy_pct, 0) / 5
```

若 CPI 缺失，则 `cpi_pressure_factor = 1`。

五个 raw loss 分别 min-max 标准化为 `consumer_loss`、`refinery_loss`、`cpi_loss`、`volatility_loss`、`security_loss`。基准权重下：

```text
total_loss =
0.25 * consumer_loss
+ 0.20 * refinery_loss
+ 0.25 * cpi_loss
+ 0.15 * volatility_loss
+ 0.15 * security_loss
```

全样本福利损失 `J` 为各窗口 `total_loss` 之和。

## 3. 五个损失项的经济含义

- 消费者损失：上调越大，居民和企业终端用油成本越高。
- 炼油企业损失：实际调价偏离理论成本调价越大，炼厂利润保障越弱。
- CPI 冲击损失：油价上调在 CPI 压力高时会带来更强通胀冲击。
- 波动损失：相邻窗口调价动作变化越大，对市场预期和经营计划冲击越强。
- 能源安全损失：长期未传导缺口越大，越可能形成供应稳定和成本积压压力。

## 4. 为什么要标准化

五类 raw loss 都是平方项，但数量级不同。例如累计未传导缺口的平方可能远大于单期消费者损失。若直接加权，会被量纲和尺度最大的分项主导。因此先用 min-max 标准化，把每个分项压缩到 0 到 1，再按权重求和。

当前标准化在每个策略样本内部完成，便于比较同一策略下不同窗口的损失结构；跨策略比较时应把结果理解为“在本损失构造下的相对评价”，后续可补充全策略联合标准化作为稳健性检验。

## 5. 各策略结果比较

基准权重下，策略总福利损失排名如下：

| 排名 | 策略 | 总损失 | 说明 |
| ---: | --- | ---: | --- |
| 1 | S1_full_pass | 5.16 | 理论调价完全传导 |
| 2 | S4_grid_best_fixed_lambda | 5.16 | 网格搜索最优 `lambda=1`，等价于 S1 |
| 3 | S5_grid_best_segmented | 10.42 | 最优分段：small=0.9, medium=0.8, large=0.7, extreme=0.4 |
| 4 | S0_current | 12.36 | 现实中的现行机制 |
| 5 | S2_fixed_70 | 14.57 | 固定 70% 平滑传导 |
| 6 | S3_segmented_smoothing | 14.60 | 预设分段平滑传导 |

S1/S4 的优势来自理论成本完全传导，炼油企业损失和累计未传导安全损失为 0。S5 在保留成本传导的同时，对大幅波动作了平滑处理，虽然总损失高于完全传导，但比现行机制低。

## 6. 最优策略

在当前福利损失函数和基准权重下，数学意义上的最优策略是 S1_full_pass；S4 的最优固定比例为 `lambda=1`，因此与 S1 等价。

如果论文强调“政策可落地与平滑调控”，更适合写入政策建议的是 S5_grid_best_segmented。它的最优组合为：

```text
lambda_small = 0.9
lambda_medium = 0.8
lambda_large = 0.7
lambda_extreme = 0.4
```

这说明小幅波动应接近充分传导，中等和大幅波动逐步平滑，极端波动应显著削峰。

## 7. 不同策略优缺点

- S0_current：真实机制，可作为历史基准；但在当前损失函数下总损失高于 S1/S4/S5。
- S1_full_pass：总损失最低，成本传导充分；但大幅上调可能带来消费者和 CPI 冲击，政策接受度较弱。
- S2_fixed_70：简单可解释；但固定比例过于机械，累计未传导缺口较大。
- S3_segmented_smoothing：有分段思路；但预设参数偏保守，福利表现不如网格搜索后的 S5。
- S4_grid_best_fixed_lambda：用网格证明固定比例最优点为 `lambda=1`；实质上退化为完全传导。
- S5_grid_best_segmented：兼顾解释性和政策弹性，是更适合提炼为调价规则的候选方案。

## 8. 权重敏感性分析

五组权重情景下，结论总体稳定：

- S1_full_pass 始终排名第 1；
- S4_grid_best_fixed_lambda 始终排名第 2，且最优固定 `lambda` 始终为 `1`；
- S5_grid_best_segmented 始终排名第 3；
- S0_current 始终排名第 4；
- S2_fixed_70 与 S3_segmented_smoothing 在不同权重下位次略有互换。

分段策略最优参数也较稳定：

- `lambda_small = 0.9`；
- `lambda_medium = 0.8`；
- `lambda_extreme = 0.4`；
- `lambda_large` 在基准和民生优先情景为 `0.7`，在其他情景为 `0.6`。

这说明“充分传导优先、极端波动削峰”的结论较稳健。

## 9. 当前模型局限

- 福利损失函数仍是简化型，尚未使用真实消费量、销量、炼厂利润或财政税费数据；
- 标准化方式会影响跨策略损失比较，后续需做联合标准化和 raw loss 加权检验；
- CPI 冲击只用 CPI 同比构造压力因子，没有估计油价到 CPI 的实际弹性；
- 能源安全损失以累计未传导缺口代理，尚未纳入库存、进口依赖、供应扰动等变量；
- 策略只在历史理论调价序列上回放，不包含市场参与者预期反馈；
- 极端高油价样本不足，无法充分评估 `>=1500` 元/吨理论调价区间。

## 10. 下一步工作

下一步建议：

- 把 S5 的最优分段参数提炼成论文中的简化调价规则；
- 对 `basket_window_change`、`brent_wti_avg_window_change` 重新计算理论调价，做稳健性检验；
- 对福利权重做更密集的扰动分析；
- 引入成品油消费量或销量，把元/吨损失转化为总量经济损失；
- 补充汇率、税费、炼厂利润、库存或进口依赖数据；
- 在不做复杂动态规划的前提下，继续做多情景模拟和政策规则对比。
