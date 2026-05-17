from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
START_DATE = "2016-01-01"
END_DATE = "2026-05-13"
START_MONTH = "2016-01"
END_MONTH = "2026-04"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update({"User-Agent": USER_AGENT})
    return s


HTTP = session()


def calendar_dates() -> pd.DataFrame:
    return pd.DataFrame({"date": pd.date_range(START_DATE, END_DATE, freq="D")})


def calendar_months() -> pd.DataFrame:
    months = pd.period_range(START_MONTH, END_MONTH, freq="M").astype(str)
    return pd.DataFrame({"month": months})


def clean_number(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--", "NA", "N/A", "nan", "None"}:
        return pd.NA
    try:
        return float(text)
    except ValueError:
        return pd.NA


def round_nullable(series: pd.Series, digits: int) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").round(digits)


def nullable_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").round(0).astype("Int64")


def write_csv(df: pd.DataFrame, filename: str) -> None:
    out = ROOT / filename
    df.to_csv(out, index=False, encoding="utf-8-sig", na_rep="")


def read_fred_series(series_id: str, fallback: Path) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        resp = HTTP.get(url, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if len(df.columns) >= 2:
            df = df.rename(columns={df.columns[0]: "date", df.columns[1]: "value"})
        else:
            raise ValueError("unexpected FRED CSV shape")
    except Exception:
        df = pd.read_csv(fallback).rename(columns={"Date": "date", "Price": "value"})

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
    return make_daily_observed_range(df.dropna(subset=["date"])[["date", "value"]])


def read_opec_basket(fallback: Path) -> pd.DataFrame:
    df = pd.read_csv(fallback, skiprows=1, header=None, names=["date", "value"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return make_daily_observed_range(df.dropna(subset=["date"])[["date", "value"]])


def make_daily_observed_range(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    clean = clean.dropna(subset=["value"])
    if clean.empty:
        return pd.DataFrame(columns=["date", "value"])
    idx = pd.date_range(clean["date"].min(), clean["date"].max(), freq="D")
    out = clean.set_index("date").reindex(idx).ffill()
    out.index.name = "date"
    return out.reset_index()[["date", "value"]]


def build_oil_price_daily() -> pd.DataFrame:
    base = calendar_dates()
    sources = {
        "brent_usd_bbl": read_fred_series("DCOILBRENTEU", ROOT / "data/raw/brent_daily.csv"),
        "wti_usd_bbl": read_fred_series("DCOILWTICO", ROOT / "data/raw/wti_daily.csv"),
        "opec_usd_bbl": read_opec_basket(ROOT / "data/raw/basket_oil_daily.csv"),
    }

    out = base.copy()
    for column, df in sources.items():
        out = out.merge(df.rename(columns={"value": column}), on="date", how="left")
        out[column] = round_nullable(out[column], 2)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out


ASKCI_MONTH_URL = "https://s.askci.com/data/MonthDetail/Index"


def parse_cn_month(text: str) -> str | None:
    match = re.search(r"(\d{4})\D+(\d{1,2})\D*", str(text))
    if not match:
        return None
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"


def fetch_askci_output_tons(zbid: str) -> pd.DataFrame:
    params = {
        "zbId": zbid,
        "type": "2",
        "StartTime": "2016-01-01",
        "EndTime": "2026-04-01",
        "CityCode": "",
    }
    resp = HTTP.get(ASKCI_MONTH_URL, params=params, timeout=40)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    tables = pd.read_html(io.StringIO(resp.text))
    if not tables:
        return pd.DataFrame(columns=["month", "tons"])

    table = None
    for candidate in tables:
        cols = [str(c) for c in candidate.columns]
        if "日期" in cols and "当月产量(万吨)" in cols:
            table = candidate
            break
    if table is None:
        table = tables[0]

    table = table.copy()
    table["month"] = table["日期"].map(parse_cn_month)
    table["value_10k_ton"] = table["当月产量(万吨)"].map(clean_number)
    table["tons"] = nullable_int(pd.to_numeric(table["value_10k_ton"], errors="coerce") * 10000)
    return table.dropna(subset=["month"])[["month", "tons"]].drop_duplicates("month")


def build_product_consumption_monthly() -> pd.DataFrame:
    out = calendar_months()
    gasoline = fetch_askci_output_tons("a030107").rename(columns={"tons": "gasoline_output_ton"})
    diesel = fetch_askci_output_tons("a030109").rename(columns={"tons": "diesel_output_ton"})
    out = out.merge(gasoline, on="month", how="left").merge(diesel, on="month", how="left")
    for column in [
        "gasoline_import_ton",
        "diesel_import_ton",
        "gasoline_export_ton",
        "diesel_export_ton",
    ]:
        out[column] = pd.NA
    return out[
        [
            "month",
            "gasoline_output_ton",
            "diesel_output_ton",
            "gasoline_import_ton",
            "diesel_import_ton",
            "gasoline_export_ton",
            "diesel_export_ton",
        ]
    ]


def read_crude_imports() -> pd.DataFrame:
    path = ROOT / "data/raw/china_crude_oil_import_monthly.csv"
    df = pd.read_csv(path, skiprows=1)
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m")
    df["crude_import_ton"] = nullable_int(pd.to_numeric(df["import_volume_10k_tons"], errors="coerce") * 10000)
    df["crude_import_value_usd"] = nullable_int(
        pd.to_numeric(df["import_amount_10k_usd"], errors="coerce") * 10000
    )
    return df[["month", "crude_import_ton", "crude_import_value_usd"]]


def build_crude_supply_monthly() -> pd.DataFrame:
    out = calendar_months()
    imports = read_crude_imports()
    crude_output = fetch_askci_output_tons("a030102").rename(columns={"tons": "crude_output_ton"})
    processing = fetch_askci_output_tons("a030106").rename(columns={"tons": "crude_processing_ton"})
    out = (
        out.merge(imports, on="month", how="left")
        .merge(crude_output, on="month", how="left")
        .merge(processing, on="month", how="left")
    )
    out["crude_export_ton"] = pd.NA
    return out[
        [
            "month",
            "crude_import_ton",
            "crude_import_value_usd",
            "crude_output_ton",
            "crude_export_ton",
            "crude_processing_ton",
        ]
    ]


def fetch_nbs_index_series(cid: str, indicator_id: str) -> pd.DataFrame:
    url = "https://data.stats.gov.cn/dg/website/publicrelease/web/external/getEsDataByCidAndDt"
    payload = {
        "cid": cid,
        "indicatorIds": [indicator_id],
        "daCatalogId": "",
        "das": [{"text": "全国", "value": "000000000000"}],
        "dts": ["201601MM-202604MM"],
        "showType": "1",
        "rootId": "fc982599aa684be7969d7b90b1bd0e84",
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://data.stats.gov.cn/dg/website/index.htm",
        "Content-Type": "application/json;charset=UTF-8",
    }
    resp = HTTP.post(url, json=payload, headers=headers, timeout=40)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    rows = []
    for item in data:
        code = item.get("code")
        values = item.get("values") or []
        if not code or not values:
            continue
        raw_value = values[0].get("value")
        value = clean_number(raw_value)
        rows.append({"month": f"{code[:4]}-{code[4:6]}", "index_value": value})
    return pd.DataFrame(rows)


def index_to_percent(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["month", column])
    out = df.copy()
    out[column] = round_nullable(pd.to_numeric(out["index_value"], errors="coerce") - 100, 4)
    return out[["month", column]]


def parse_ak_month(series: pd.Series) -> pd.Series:
    return series.astype(str).map(parse_cn_month)


def fetch_ak_cpi() -> pd.DataFrame:
    import akshare as ak

    df = ak.macro_china_cpi()
    out = pd.DataFrame(
        {
            "month": parse_ak_month(df["月份"]),
            "cpi_yoy": pd.to_numeric(df["全国-同比增长"], errors="coerce"),
            "cpi_mom": pd.to_numeric(df["全国-环比增长"], errors="coerce"),
        }
    )
    return out.dropna(subset=["month"])


def build_macro_price_monthly() -> pd.DataFrame:
    out = calendar_months()
    try:
        out = out.merge(fetch_ak_cpi(), on="month", how="left")
    except Exception:
        fallback = pd.read_csv(ROOT / "data/raw/china_cpi_ppi_monthly.csv", skiprows=1)
        fallback["month"] = pd.to_datetime(fallback["date"], errors="coerce").dt.strftime("%Y-%m")
        fallback["cpi_yoy"] = pd.to_numeric(fallback["cpi_yoy_pct"], errors="coerce")
        out = out.merge(fallback[["month", "cpi_yoy"]], on="month", how="left")
        out["cpi_mom"] = pd.NA

    nbs_specs = {
        "cpi_transport_yoy": ("5c7452825c7c4dcba391db5ca7f335c5", "e6e42078f30e483b899b2701a766909a"),
        "cpi_transport_mom": ("b4fad2cf9e0e4af7815b7e9e2e95c5c7", "3be5e392733749b58f6b87fe117fe1f9"),
        "ppi_yoy": ("60e8b361f11c4a878c652a6487a25561", "150633e52b9a470a9a9fd1b296dd6c5b"),
        "ppi_mom": ("677cfbb4f06941af8c1761c4804e58cf", "e64079bae9064aebad1c4c5fe0c8a6ef"),
        "ppi_fuel_power_yoy": ("50f683df1f8b4da9831b7047d5091571", "25290193d8e24b76963503326e690cb0"),
    }
    for column, (cid, indicator_id) in nbs_specs.items():
        try:
            series = index_to_percent(fetch_nbs_index_series(cid, indicator_id), column)
        except Exception:
            series = pd.DataFrame(columns=["month", column])
        out = out.merge(series, on="month", how="left")

    for column in [
        "cpi_yoy",
        "cpi_mom",
        "cpi_transport_yoy",
        "cpi_transport_mom",
        "ppi_yoy",
        "ppi_mom",
        "ppi_fuel_power_yoy",
    ]:
        out[column] = round_nullable(out[column], 4)

    return out[
        [
            "month",
            "cpi_yoy",
            "cpi_mom",
            "cpi_transport_yoy",
            "cpi_transport_mom",
            "ppi_yoy",
            "ppi_mom",
            "ppi_fuel_power_yoy",
        ]
    ]


def build_cpi_target_annual() -> pd.DataFrame:
    targets = {
        2016: 3.0,
        2017: 3.0,
        2018: 3.0,
        2019: 3.0,
        2020: 3.5,
        2021: 3.0,
        2022: 3.0,
        2023: 3.0,
        2024: 3.0,
        2025: 2.0,
        2026: 2.0,
    }
    return pd.DataFrame({"year": list(targets.keys()), "cpi_target": list(targets.values())})


def build_expectation_search_daily() -> pd.DataFrame:
    keywords = ["油价上涨", "油价调整", "汽油涨价", "柴油涨价", "通胀", "物流成本"]
    dates = pd.date_range(START_DATE, END_DATE, freq="D").strftime("%Y-%m-%d")
    return pd.DataFrame(
        [{"date": date, "keyword": keyword, "search_index": pd.NA} for date in dates for keyword in keywords]
    )


def build_oil_news_sentiment_daily() -> pd.DataFrame:
    out = calendar_dates()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out["total_news"] = pd.NA
    out["negative_news"] = pd.NA
    out["positive_news"] = pd.NA
    out["sentiment_score"] = pd.NA
    return out[["date", "total_news", "negative_news", "positive_news", "sentiment_score"]]


def non_null_counts(df: pd.DataFrame, columns: Iterable[str]) -> dict[str, int]:
    return {col: int(df[col].notna().sum()) for col in columns if col in df.columns}


def write_notes(summary: dict[str, dict[str, int]]) -> None:
    notes = {
        "generated_on": "2026-05-13",
        "timezone": "Asia/Shanghai",
        "files": summary,
        "sources": {
            "oil_price_daily": [
                "FRED/EIA daily spot prices: DCOILBRENTEU and DCOILWTICO, with local raw CSV fallback.",
                "OPEC Reference Basket daily local raw CSV fallback from the existing project source file.",
                "Trading-day quote gaps inside each source's observed range are forward-filled to produce a natural daily frequency; dates after a source's latest observed quote are left blank.",
            ],
            "product_and_crude_output": [
                "AskCI/NBS public monthly output pages via MonthDetail API: a030107 gasoline, a030109 diesel, a030102 crude oil, a030106 crude processing.",
                "NBS industrial output does not publish a separate January current-month value; Jan-Feb is usually reported as an accumulated value. The current-month field is left blank when the source table is blank.",
            ],
            "customs": [
                "Crude oil import volume and value are taken from the existing project raw customs CSV through 2024-12.",
                "Open bulk monthly gasoline/diesel import/export and crude export tonnage was not available from accessible public endpoints in this run. Those requested columns are retained with blank values.",
            ],
            "macro_price": [
                "CPI headline yoy/mom from AkShare/Eastmoney public data.",
                "PPI yoy/mom and fuel-power purchase price yoy from NBS publicrelease API.",
                "CPI transport yoy/mom from NBS publicrelease API is currently exposed only for 2026 months through the accessible endpoint; earlier months remain blank.",
            ],
            "cpi_target": [
                "2016-2024 targets follow the annual Government Work Report CPI targets; 2025 and 2026 are 2.0 around as verified from the published work reports.",
            ],
            "expectations_and_news": [
                "Baidu Index and WeChat Index require authenticated export access, so expectation_search_daily.csv is a structured template with blank search_index.",
                "No auditable open news corpus/classifier was available in this run for the requested Chinese oil-news sentiment counts, so oil_news_sentiment_daily.csv is a structured template with blank fields.",
            ],
        },
    }
    (ROOT / "data_acquisition_notes.json").write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    files: dict[str, pd.DataFrame] = {
        "oil_price_daily.csv": build_oil_price_daily(),
        "product_consumption_monthly.csv": build_product_consumption_monthly(),
        "crude_supply_monthly.csv": build_crude_supply_monthly(),
        "macro_price_monthly.csv": build_macro_price_monthly(),
        "cpi_target_annual.csv": build_cpi_target_annual(),
        "expectation_search_daily.csv": build_expectation_search_daily(),
        "oil_news_sentiment_daily.csv": build_oil_news_sentiment_daily(),
    }
    summary: dict[str, dict[str, int]] = {}
    for filename, df in files.items():
        write_csv(df, filename)
        summary[filename] = {
            "rows": int(len(df)),
            **non_null_counts(df, [col for col in df.columns if col not in {"date", "month", "year", "keyword"}]),
        }
    write_notes(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
