# Data Quality Report

## basket_oil_daily.csv

- Rows: 6022
- Columns: 2
- Field names: column_1, column_2
- Metadata line(s): 国际原油篮子价格日度数据
- Date column recognition: column_1
- Date range: 2003-01-02 to 2026-05-08
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| column_1 | 0 |
| column_2 | 0 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| column_2 | 6022 | 70.616425 | 25.551809 | 12.22 | 51.5425 | 68.74 | 88.2175 | 146.05 |

Anomaly hints:

_None._

## brent_daily.csv

- Rows: 9883
- Columns: 2
- Field names: Date, Price
- Metadata line(s): (none)
- Date column recognition: Date
- Date range: 1987-05-20 to 2026-05-01
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| Date | 0 |
| Price | 0 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Price | 9883 | 51.102119 | 32.707622 | 9.1 | 19.535 | 46.04 | 74.715 | 143.95 |

Anomaly hints:

_None._

## china_cpi_ppi_monthly.csv

- Rows: 160
- Columns: 3
- Field names: date, cpi_yoy_pct, ppi_yoy_pct
- Metadata line(s): CPI/PPI 月度数据
- Date column recognition: date
- Date range: 2013-01-01 to 2026-04-01
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| date | 0 |
| cpi_yoy_pct | 0 |
| ppi_yoy_pct | 0 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cpi_yoy_pct | 160 | 1.563125 | 1.149111 | -0.8 | 0.7 | 1.6 | 2.3 | 5.4 |
| ppi_yoy_pct | 160 | 0.14875 | 4.298588 | -5.9 | -2.625 | -1.4 | 3.15 | 13.5 |

Anomaly hints:

_None._

## china_crude_oil_import_monthly.csv

- Rows: 143
- Columns: 4
- Field names: date, import_volume_10k_tons, import_amount_10k_usd, average_price_usd_per_ton
- Metadata line(s): 中国原油进口月度数据
- Date column recognition: date
- Date range: 2013-01-01 to 2024-12-01
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| date | 0 |
| import_volume_10k_tons | 0 |
| import_amount_10k_usd | 0 |
| average_price_usd_per_ton | 0 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| import_volume_10k_tons | 143 | 3664.59972 | 1056.909123 | 100 | 2914 | 3847 | 4351 | 8609 |
| import_amount_10k_usd | 143 | 1923398.988322 | 740216.50185 | 42203 | 1332077.9 | 1876820 | 2428672.4 | 4218444.2 |
| average_price_usd_per_ton | 143 | 555.197483 | 306.947931 | 150.72 | 398.515 | 536 | 642.73 | 3617.03 |

Anomaly hints:

- average_price_usd_per_ton: 1 IQR outliers outside [-334.13, 1375.375]

## china_pmi_monthly.csv

- Rows: 160
- Columns: 4
- Field names: date, nbs_manufacturing_pmi, non_manufacturing_pmi, nbs_general_pmi
- Metadata line(s): PMI 月度数据
- Date column recognition: date
- Date range: 2013-01-01 to 2026-04-01
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| date | 0 |
| nbs_manufacturing_pmi | 0 |
| non_manufacturing_pmi | 0 |
| nbs_general_pmi | 48 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nbs_manufacturing_pmi | 160 | 50.20125 | 1.491949 | 35.7 | 49.575 | 50.2 | 51 | 52.6 |
| non_manufacturing_pmi | 160 | 52.88875 | 3.050765 | 29.6 | 51.4 | 53.75 | 54.5 | 58.2 |
| nbs_general_pmi | 112 | 52.025 | 3.175143 | 28.9 | 50.7 | 52.55 | 54 | 57 |

Anomaly hints:

- nbs_manufacturing_pmi: 1 IQR outliers outside [45.3, 55.275]
- non_manufacturing_pmi: 3 IQR outliers outside [42.1, 63.8]
- nbs_general_pmi: 1 IQR outliers outside [40.8, 63.9]

## china_refined_oil_adjustments_2013_2026.csv

- Rows: 329
- Columns: 8
- Field names: date, notice_date, gasoline_adjust_cny_per_ton, diesel_adjust_cny_per_ton, beijing_gasoline_ceiling_after_cny_per_ton, beijing_diesel_ceiling_after_cny_per_ton, notice_title, source_url
- Metadata line(s): 爬取/整理发改委调价公告的脚本
- Date column recognition: date, notice_date
- Date range: 2013-02-25 to 2026-05-09
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| date | 0 |
| notice_date | 0 |
| gasoline_adjust_cny_per_ton | 0 |
| diesel_adjust_cny_per_ton | 0 |
| beijing_gasoline_ceiling_after_cny_per_ton | 0 |
| beijing_diesel_ceiling_after_cny_per_ton | 0 |
| notice_title | 0 |
| source_url | 0 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gasoline_adjust_cny_per_ton | 329 | 3.267477 | 223.100467 | -1015 | -130 | 0 | 150 | 1160 |
| diesel_adjust_cny_per_ton | 329 | 2.24924 | 215.859284 | -975 | -125 | 0 | 145 | 1115 |
| beijing_gasoline_ceiling_after_cny_per_ton | 329 | 8790.547112 | 1062.055002 | 6765 | 8030 | 8805 | 9655 | 11615 |
| beijing_diesel_ceiling_after_cny_per_ton | 329 | 7820.942249 | 1058.458825 | 5840 | 7030 | 7815 | 8720 | 10510 |

Anomaly hints:

- gasoline_adjust_cny_per_ton: 2 IQR outliers outside [-970, 990]
- diesel_adjust_cny_per_ton: 2 IQR outliers outside [-935, 955]

## china_refined_oil_beijing_diesel_limit_series_2013_2026.csv

- Rows: 329
- Columns: 2
- Field names: column_1, column_2
- Metadata line(s): 北京柴油最高零售限价序列
- Date column recognition: column_1
- Date range: 2013-02-25 to 2026-05-09
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| column_1 | 0 |
| column_2 | 0 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| column_2 | 329 | 7820.942249 | 1058.458825 | 5840 | 7030 | 7815 | 8720 | 10510 |

Anomaly hints:

_None._

## china_refined_oil_beijing_gasoline_limit_series_2013_2026.csv

- Rows: 329
- Columns: 2
- Field names: column_1, column_2
- Metadata line(s): 北京汽油最高零售限价序列
- Date column recognition: column_1
- Date range: 2013-02-25 to 2026-05-09
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| column_1 | 0 |
| column_2 | 0 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| column_2 | 329 | 8790.547112 | 1062.055002 | 6765 | 8030 | 8805 | 9655 | 11615 |

Anomaly hints:

_None._

## china_refined_oil_parse_review_2013_2026.csv

- Rows: 0
- Columns: 6
- Field names: date, notice_date, title, url, status, text_excerpt
- Metadata line(s): (none)
- Date column recognition: (none)
- Date range: (not available) to (not available)
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| date | 0 |
| notice_date | 0 |
| title | 0 |
| url | 0 |
| status | 0 |
| text_excerpt | 0 |

Anomaly hints:

_None._

## wti_daily.csv

- Rows: 10153
- Columns: 2
- Field names: Date, Price
- Metadata line(s): (none)
- Date column recognition: Date
- Date range: 1986-01-02 to 2026-05-04
- Duplicate dates on primary date column: 0

Missing values:

| column | missing_count |
| --- | --- |
| Date | 0 |
| Price | 0 |

Numeric summary:

| column | count | mean | std | min | q1 | median | q3 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Price | 10153 | 48.31667 | 29.504599 | -36.98 | 20.33 | 43.04 | 71.3 | 145.31 |

Anomaly hints:

- Price: 1 non-positive values

## Special Check: Crude Oil Import Average Price

- china_crude_oil_import_monthly.csv: 2 flagged monthly records

| date | import_volume_10k_tons | import_amount_10k_usd | average_price_usd_per_ton | recalc_avg_price_usd_per_ton | difference | flags |
| --- | --- | --- | --- | --- | --- | --- |
| 2021-01-01 | 4459 | 1612834.7 | 3617.03 | 361.703229 | 3255.326771 | reported average price differs from recalculated value; reported average price is an IQR outlier |
| 2024-03-01 | 4905 | 2937969.6 | 588.55 | 598.974434 | -10.424434 | reported average price differs from recalculated value |
