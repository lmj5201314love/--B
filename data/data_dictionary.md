# 数据字典

本字典覆盖当前阶段用于构建调价窗口级建模主表的原始数据。原始文件均保留在 `data/raw/`，清洗和派生结果写入 `data/processed/`。

## data/raw/basket_oil_daily.csv

- 含义：国际原油篮子价格日度序列，作为我国成品油调价机制复现的候选国际油价代理变量。
- 频率：日度交易日/报价日。
- 日期范围：2003-01-02 至 2026-05-08。
- 原始结构：首行为说明文字，后续两列无正式表头。
- 字段：
  - `column_1`：日期，格式 `YYYY-MM-DD`。
  - `column_2`：原油篮子价格，单位为美元/桶。
- 后续用途：清洗为 `basket_usd_per_bbl`，参与 10 个有效交易日窗口均值、窗口变化和基线机制复现。

## data/raw/brent_daily.csv

- 含义：Brent 原油日度价格。
- 频率：日度交易日/报价日。
- 日期范围：1987-05-20 至 2026-05-01。
- 字段：
  - `Date`：日期，格式 `YYYY-MM-DD`。
  - `Price`：Brent 原油价格，单位为美元/桶。
- 后续用途：清洗为 `brent_usd_per_bbl`，用于 Brent 单独代理，以及 Brent/WTI 平均与加权代理。

## data/raw/wti_daily.csv

- 含义：WTI 原油日度价格。
- 频率：日度交易日/报价日。
- 日期范围：1986-01-02 至 2026-05-04。
- 字段：
  - `Date`：日期，格式 `YYYY-MM-DD`。
  - `Price`：WTI 原油价格，单位为美元/桶。
- 后续用途：清洗为 `wti_usd_per_bbl`，用于 WTI 单独代理，以及 Brent/WTI 平均与加权代理。
- 质量提示：2020 年存在负油价记录，质量报告仅标记不删除。

## data/raw/china_refined_oil_adjustments_2013_2026.csv

- 含义：我国成品油调价窗口公告整理数据。
- 频率：调价窗口级。
- 日期范围：2013-02-25 至 2026-05-09。
- 原始结构：首行为说明文字，第二行为正式表头。
- 字段：
  - `date`：调价执行日期。
  - `notice_date`：公告发布日期。
  - `gasoline_adjust_cny_per_ton`：汽油调价幅度，单位为元/吨。
  - `diesel_adjust_cny_per_ton`：柴油调价幅度，单位为元/吨。
  - `beijing_gasoline_ceiling_after_cny_per_ton`：调价后北京汽油最高零售限价，单位为元/吨。
  - `beijing_diesel_ceiling_after_cny_per_ton`：调价后北京柴油最高零售限价，单位为元/吨。
  - `notice_title`：公告标题。
  - `source_url`：公告来源链接。
- 后续用途：生成平均调价幅度、调价方向、是否调价、平均最高限价，并作为建模主表的核心观测窗口。

## data/raw/china_cpi_ppi_monthly.csv

- 含义：中国 CPI/PPI 月度同比指标。
- 频率：月度。
- 日期范围：2013-01-01 至 2026-04-01。
- 原始结构：首行为说明文字，第二行为正式表头。
- 字段：
  - `date`：月份日期，通常为月初日期。
  - `cpi_yoy_pct`：居民消费价格指数同比，单位为百分比。
  - `ppi_yoy_pct`：工业生产者出厂价格指数同比，单位为百分比。
- 后续用途：按 `month` 合并至调价窗口主表，作为通胀和工业价格环境变量。

## data/raw/china_crude_oil_import_monthly.csv

- 含义：中国原油进口月度数量、金额与均价。
- 频率：月度。
- 日期范围：2013-01-01 至 2024-12-01。
- 原始结构：首行为说明文字，第二行为正式表头。
- 字段：
  - `date`：月份日期，通常为月初日期。
  - `import_volume_10k_tons`：原油进口量，单位为万吨。
  - `import_amount_10k_usd`：原油进口金额，单位为万美元。
  - `average_price_usd_per_ton`：原油进口平均价格，单位为美元/吨。
- 后续用途：按 `month` 合并至调价窗口主表，作为进口成本和外部供给环境变量。
- 质量提示：质量检查脚本会重算 `import_amount_10k_usd / import_volume_10k_tons`，并标记与报告均价差异过大的月份。

## data/raw/china_pmi_monthly.csv

- 含义：中国 PMI 月度指标。
- 频率：月度。
- 日期范围：2013-01-01 至 2026-04-01。
- 原始结构：首行为说明文字，第二行为正式表头。
- 字段：
  - `date`：月份日期，通常为月初日期。
  - `nbs_manufacturing_pmi`：国家统计局制造业 PMI，指数点。
  - `non_manufacturing_pmi`：非制造业 PMI，指数点。
  - `nbs_general_pmi`：综合 PMI，指数点。
- 后续用途：按 `month` 合并至调价窗口主表，作为经济景气度变量。
- 质量提示：`nbs_general_pmi` 在早期月份存在缺失，质量报告会记录缺失数量。

## data/raw/china_refined_oil_beijing_gasoline_limit_series_2013_2026.csv

- 含义：北京汽油最高零售限价序列。
- 频率：调价窗口级。
- 日期范围：2013-02-25 至 2026-05-09。
- 原始结构：首行为说明文字，后续两列无正式表头。
- 字段：
  - `column_1`：调价执行日期。
  - `column_2`：北京汽油最高零售限价，单位为元/吨。
- 后续用途：与公告主表中的北京汽油限价字段交叉核验，并用于限价时间序列图。

## data/raw/china_refined_oil_beijing_diesel_limit_series_2013_2026.csv

- 含义：北京柴油最高零售限价序列。
- 频率：调价窗口级。
- 日期范围：2013-02-25 至 2026-05-09。
- 原始结构：首行为说明文字，后续两列无正式表头。
- 字段：
  - `column_1`：调价执行日期。
  - `column_2`：北京柴油最高零售限价，单位为元/吨。
- 后续用途：与公告主表中的北京柴油限价字段交叉核验，并用于限价时间序列图。
