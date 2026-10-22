# MyMagicFormula
# Python 3.14
import csv
import datetime as dt
import pandas as pd

from data_access.PipelineETL import has_minimum_annual_history
from Securities_DB.db_connection import get_connection
from analytics.FinancialAssessment import FinancialAssessment as FA
from runtime_config import get_data_root

"""
This class is designed to implement the Magic Formula investment strategy, which combines value and momentum factors
 to identify undervalued stocks with strong growth potential. Based off of Joel Greenblatt's 'Magic Formula' from 
 "The Little Book that Still Beats the Market"
"""

class MyMagicFormula:
    """
    Implements the Magic Formula investment strategy for stock selection.
    """

    def __init__(
            self,
            ticker: str,
            date: None | str = None,
            market_price_date: None | str = None,
    ):
        """
        Initializes the MyMagicFormula class with methods for return on capital, and earnings yield.
        Combines the two values for the magic formula rank.
        Pulls data from analytics.FinancialAssessment
        """
        if date is None:
            date = dt.datetime.today().strftime('%Y-%m-%d')

        assessment_kwargs = {"date": date}
        if market_price_date is not None:
            assessment_kwargs["market_price_date"] = market_price_date
        values = FA(ticker, **assessment_kwargs).magic_formula_values()
        self._quarter_date = values.get("quarter_date")
        self._annual_date = values.get("associated_annual_date")
        self.roc = values.get("return_on_capital")
        self.ey = values.get("earnings_yield")


def magic_formula_ranked_securities(
        tickers_list: None | list = None,
        date: None | str = None,
        market_price_date: None | str = None,
) -> pd.DataFrame:
    expected_columns = [
        "ticker",
        "quarter_date",
        "associated_annual_date",
        "magic_formula_rank",
        "return_on_capital_rank",
        "earnings_yield_rank",
        "total_roc_ey_score",
    ]

    if tickers_list and not isinstance(tickers_list,list):
        raise TypeError("tickers_list must be a list")
    elif not tickers_list:
        tickers_list = _eligible_magic_formula_tickers()

    if date:
        try:
            dt.datetime.fromisoformat(date)
        except (ValueError, TypeError) as e:
            print(f"Invalid date format: {e}")
            return pd.DataFrame(columns=expected_columns)
    if market_price_date:
        try:
            dt.datetime.fromisoformat(market_price_date)
        except (ValueError, TypeError) as e:
            print(f"Invalid market price date format: {e}")
            return pd.DataFrame(columns=expected_columns)

    tickers_list = sorted({
        ticker.strip().upper()
        for ticker in tickers_list
        if isinstance(ticker, str) and ticker.strip()
    })

    ranking_values = []
    for ticker in tickers_list:
        if not has_minimum_annual_history(ticker, 5):
            continue
        try:
            _magic_formula = MyMagicFormula(
                ticker,
                date=date,
                market_price_date=market_price_date,
            )
        except Exception as e:
            print(f"Error processing ticker {ticker}: {e}\n... moving to next ticker symbol...")
            continue

        ranking_values.append({
            "ticker": ticker,
            "quarter_date": _magic_formula._quarter_date,
            "associated_annual_date": _magic_formula._annual_date,
            "return_on_capital": _magic_formula.roc,
            "earnings_yield": _magic_formula.ey,
        })

    values = pd.DataFrame(ranking_values)
    if values.empty:
        return pd.DataFrame(columns=expected_columns)

    for column in ("return_on_capital", "earnings_yield"):
        values[column] = pd.to_numeric(values[column], errors="coerce")
    values = values.dropna(subset=[
        "ticker",
        "quarter_date",
        "associated_annual_date",
        "return_on_capital",
        "earnings_yield",
    ]).copy()
    if values.empty:
        return pd.DataFrame(columns=expected_columns)

    _assign_ordinal_rank(
        values,
        value_column="return_on_capital",
        rank_column="return_on_capital_rank",
    )
    _assign_ordinal_rank(
        values,
        value_column="earnings_yield",
        rank_column="earnings_yield_rank",
    )
    values["total_roc_ey_score"] = (
        values["return_on_capital_rank"]
        + values["earnings_yield_rank"]
    )
    values = values.sort_values(
        [
            "total_roc_ey_score",
            "return_on_capital_rank",
            "earnings_yield_rank",
            "ticker",
        ],
        kind="stable",
    ).reset_index(drop=True)
    values["magic_formula_rank"] = range(1, len(values) + 1)
    return values.loc[:, expected_columns]


def _assign_ordinal_rank(
        frame: pd.DataFrame,
        value_column: str,
        rank_column: str,
) -> None:
    ordered_indices = frame.sort_values(
        [value_column, "ticker"],
        ascending=[False, True],
        kind="stable",
    ).index
    ranks = pd.Series(
        range(1, len(ordered_indices) + 1),
        index=ordered_indices,
        dtype=int,
    )
    frame[rank_column] = ranks


MAGIC_FORMULA_MIN_REVENUE = 1e8
MAGIC_FORMULA_NO_USE_INDUSTRIES = ('INSURANCE', 'REIT', 'UTILITIES', 'INVESTMENT')
MAGIC_FORMULA_NO_USE_SECTORS = ('FINANCIAL SERVICES', 'FINANCIALS', 'UTILITIES')


def _eligible_magic_formula_tickers(ticker_list:list|None=None) -> list[str]:
    from data_access.CompanyDetails import CompanyDetails as CD
    from data_access.PipelineETL import has_minimum_annual_history
    if ticker_list and isinstance(ticker_list, list) and len(ticker_list) > 0:
        tickerlist = ticker_list
    else:
        tickerlist = CD().all_sec_tickers().get('ticker').tolist()
    c = 1
    valid_mfr_tickers = []

    for ticker in tickerlist:

        if not has_minimum_annual_history(ticker,5):
            print(f"Not enough history for {ticker}")
            continue

        comp_detail = CD(ticker)
        comp_details = comp_detail.get_details() or {}

        try:
            fa = FA(ticker).to_dict()
        except Exception as e:
            print(f"Skipping {ticker}: unable to build FinancialAssessment ({e})")
            continue

        if fa is None or not isinstance(fa, dict):
            continue

        date = fa.get('analysis_date', None)
        if date is None:
            continue

        try:
            eps = fa.get('eps', 0.0)
            share_price = fa.get('market_price_for_period', 0.0)
            revenue = fa.get('total_sales_services', 0.0)
            sector = fa.get('sector', '')
            industry = fa.get('industry', '')
            currency = comp_details.get('Currency', '')
            country = (comp_details.get('Address', '') or '').upper()

        except Exception as e:
            print(f"Not sufficient data for {ticker}: {e}")
            continue

        if not revenue or revenue < MAGIC_FORMULA_MIN_REVENUE:
            continue

        pe_ratio = (share_price / eps) if eps > 0 else None
        if pe_ratio is None or pe_ratio < 5:
            continue

        if not currency or currency != 'USD':
            continue

        if not country or 'UNITED STATES' not in country:
            continue

        if not sector or sector in MAGIC_FORMULA_NO_USE_SECTORS:
            continue

        if any((no in industry for no in MAGIC_FORMULA_NO_USE_INDUSTRIES)):
            continue

        valid_mfr_tickers.append(ticker)

        if c%10==0:
            print(f"{int(c)}")
        c += 1

    return valid_mfr_tickers


def _load_magic_formula_market_cap_groups(tickers: list[str]) -> pd.DataFrame:
    tickers = sorted({ticker.upper() for ticker in tickers if isinstance(ticker, str) and ticker})
    if not tickers:
        return pd.DataFrame(columns=['ticker', 'marketCapGroup'])

    frames: list[pd.DataFrame] = []
    conn = get_connection(readonly=True)
    try:
        for start in range(0, len(tickers), 500):
            chunk = tickers[start:start + 500]
            placeholders = ",".join(["?"] * len(chunk))
            sql = f"""
                SELECT ticker, marketCapGroup
                FROM market_capitalization
                WHERE ticker IN ({placeholders})
            """
            frame = pd.read_sql_query(sql, conn, params=chunk)
            frames.append(frame)
    finally:
        conn.close()

    if not frames:
        return pd.DataFrame(columns=['ticker', 'marketCapGroup'])

    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return pd.DataFrame(columns=['ticker', 'marketCapGroup'])

    df['ticker'] = df['ticker'].astype(str).str.upper()
    df = df.dropna(subset=['ticker', 'marketCapGroup']).copy()
    df['marketCapGroup'] = df['marketCapGroup'].astype(str).str.strip().str.title()
    df = df[df['marketCapGroup'].ne('Nan') & df['marketCapGroup'].ne('None')]
    df = df.drop_duplicates(subset=['ticker'])
    return df[['ticker', 'marketCapGroup']].sort_values('ticker').reset_index(drop=True)


def magic_formula_symbols_from_db(market_cap_group: str | None = None) -> list[str]:
    sql = """
        SELECT ticker, marketCapGroup
        FROM magic_formula_symbols
        WHERE ticker IS NOT NULL AND ticker != ''
    """
    params: list[str] = []
    if market_cap_group is not None:
        sql += " AND marketCapGroup = ?"
        params.append(str(market_cap_group).strip().title())

    conn = get_connection(readonly=True)
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return []
    finally:
        conn.close()

    if df.empty:
        return []

    df['ticker'] = df['ticker'].astype(str).str.upper()
    return sorted(df['ticker'].dropna().unique().tolist())


def populate_magic_formula_symbols_table() -> pd.DataFrame:
    eligible_tickers = _eligible_magic_formula_tickers()
    eligible_caps = _load_magic_formula_market_cap_groups(eligible_tickers)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM magic_formula_symbols")
        if not eligible_caps.empty:
            cur.executemany(
                "INSERT OR REPLACE INTO magic_formula_symbols (ticker, marketCapGroup) VALUES (?, ?)",
                list(eligible_caps.itertuples(index=False, name=None)),
            )
        conn.commit()
    finally:
        conn.close()

    with open(get_data_root() / 'notebooks' / 'magic_formula_tickers.csv', 'w', newline='') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerow(eligible_caps['ticker'].tolist())

    return eligible_caps


def _vetted_ticker_symbols_to_file():
    eligible_caps = populate_magic_formula_symbols_table()
    if eligible_caps.empty:
        return print("0 valid ticker symbols saved to table.")
    return print(f"{len(eligible_caps)} valid ticker symbols saved to table.")
