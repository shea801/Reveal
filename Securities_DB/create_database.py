# Python 3.14
# created: May 13, 2026
# Database creation and population script for Investment securities data
# Uses SQLite for local storage with option for future Docker/PostgreSQL migration

import sqlite3
import os

from runtime_config import get_data_root, investment_db_path
from data_access.file_parsing import load_json_from_file_safe
from data_ingestion.TickerFileSearch import TickerSearch
from Securities_DB.ohlcv_database import (
    ensure_ohlcv_schema,
    upsert_ohlcv_payload,
)

# ─── Company Details column definitions ───────────────────────────────────────
# Columns that should be stored as TEXT
TEXT_COLS = {
    'Symbol', 'AssetType', 'Name', 'Description', 'CIK', 'Exchange',
    'Currency', 'Country', 'Sector', 'Industry', 'Address', 'OfficialSite',
    'FiscalYearEnd',
}
# Columns that should be stored as DATE (YYYY-MM-DD strings)
DATE_COLS = {'LatestQuarter', 'DividendDate', 'ExDividendDate'}
# Columns that are large integers
BIGINT_COLS = {
    'MarketCapitalization', 'EBITDA', 'RevenueTTM', 'GrossProfitTTM',
    'SharesOutstanding', 'SharesFloat',
    'AnalystRatingStrongBuy', 'AnalystRatingBuy', 'AnalystRatingHold',
    'AnalystRatingSell', 'AnalystRatingStrongSell',
}
# Everything else in company_details is REAL (float)

# All 56 company_details keys in order
COMPANY_DETAILS_KEYS = [
    'Symbol', 'AssetType', 'Name', 'Description', 'CIK', 'Exchange',
    'Currency', 'Country', 'Sector', 'Industry', 'Address', 'OfficialSite',
    'FiscalYearEnd', 'LatestQuarter', 'MarketCapitalization', 'EBITDA',
    'PERatio', 'PEGRatio', 'BookValue', 'DividendPerShare', 'DividendYield',
    'EPS', 'RevenuePerShareTTM', 'ProfitMargin', 'OperatingMarginTTM',
    'ReturnOnAssetsTTM', 'ReturnOnEquityTTM', 'RevenueTTM', 'GrossProfitTTM',
    'DilutedEPSTTM', 'QuarterlyEarningsGrowthYOY', 'QuarterlyRevenueGrowthYOY',
    'AnalystTargetPrice', 'AnalystRatingStrongBuy', 'AnalystRatingBuy',
    'AnalystRatingHold', 'AnalystRatingSell', 'AnalystRatingStrongSell',
    'TrailingPE', 'ForwardPE', 'PriceToSalesRatioTTM', 'PriceToBookRatio',
    'EVToRevenue', 'EVToEBITDA', 'Beta', '52WeekHigh', '52WeekLow',
    '50DayMovingAverage', '200DayMovingAverage', 'SharesOutstanding',
    'SharesFloat', 'PercentInsiders', 'PercentInstitutions',
    'DividendDate', 'ExDividendDate',
]

# Financial statement column lists
BALANCE_COLS = [
    'fiscalDateEnding', 'reportedCurrency', 'totalAssets', 'totalCurrentAssets',
    'cashAndCashEquivalentsAtCarryingValue', 'cashAndShortTermInvestments',
    'inventory', 'currentNetReceivables', 'totalNonCurrentAssets',
    'propertyPlantEquipment', 'accumulatedDepreciationAmortizationPPE',
    'intangibleAssets', 'intangibleAssetsExcludingGoodwill', 'goodwill',
    'investments', 'longTermInvestments', 'shortTermInvestments',
    'otherCurrentAssets', 'otherNonCurrentAssets', 'totalLiabilities',
    'totalCurrentLiabilities', 'currentAccountsPayable', 'deferredRevenue',
    'currentDebt', 'shortTermDebt', 'totalNonCurrentLiabilities',
    'capitalLeaseObligations', 'longTermDebt', 'currentLongTermDebt',
    'longTermDebtNoncurrent', 'shortLongTermDebtTotal', 'otherCurrentLiabilities',
    'otherNonCurrentLiabilities', 'totalShareholderEquity', 'treasuryStock',
    'retainedEarnings', 'commonStock', 'commonStockSharesOutstanding',
]

CASH_FLOW_COLS = [
    'fiscalDateEnding', 'reportedCurrency', 'operatingCashflow',
    'paymentsForOperatingActivities', 'proceedsFromOperatingActivities',
    'changeInOperatingLiabilities', 'changeInOperatingAssets',
    'depreciationDepletionAndAmortization', 'capitalExpenditures',
    'changeInReceivables', 'changeInInventory', 'profitLoss',
    'cashflowFromInvestment', 'cashflowFromFinancing',
    'proceedsFromRepaymentsOfShortTermDebt', 'paymentsForRepurchaseOfCommonStock',
    'paymentsForRepurchaseOfEquity', 'paymentsForRepurchaseOfPreferredStock',
    'dividendPayout', 'dividendPayoutCommonStock', 'dividendPayoutPreferredStock',
    'proceedsFromIssuanceOfCommonStock',
    'proceedsFromIssuanceOfLongTermDebtAndCapitalSecuritiesNet',
    'proceedsFromIssuanceOfPreferredStock', 'proceedsFromRepurchaseOfEquity',
    'proceedsFromSaleOfTreasuryStock', 'stockBasedCompensation',
    'changeInCashAndCashEquivalents', 'changeInExchangeRate', 'netIncome',
]

INCOME_COLS = [
    'fiscalDateEnding', 'reportedCurrency', 'grossProfit', 'totalRevenue',
    'costOfRevenue', 'costofGoodsAndServicesSold', 'operatingIncome',
    'sellingGeneralAndAdministrative', 'researchAndDevelopment',
    'operatingExpenses', 'investmentIncomeNet', 'netInterestIncome',
    'interestIncome', 'interestExpense', 'nonInterestIncome',
    'otherNonOperatingIncome', 'depreciation', 'depreciationAndAmortization',
    'incomeBeforeTax', 'incomeTaxExpense', 'interestAndDebtExpense',
    'netIncomeFromContinuingOperations', 'comprehensiveIncomeNetOfTax',
    'ebit', 'ebitda', 'netIncome',
]

EARNINGS_ANNUAL_COLS = ['fiscalDateEnding', 'reportedEPS']

EARNINGS_QUARTERLY_COLS = [
    'fiscalDateEnding', 'reportedDate', 'reportedEPS', 'estimatedEPS',
    'surprise', 'surprisePercentage', 'reportTime',
]

MARKET_CAP_COLS = ['ticker','marketCapitalization','marketCapGroup']

def _col_type_company_details(col_name):
    """Return SQLite column type for a company_details key."""
    if col_name in TEXT_COLS:
        return 'TEXT'
    if col_name in DATE_COLS:
        return 'TEXT'  # store YYYY-MM-DD as TEXT in SQLite
    if col_name in BIGINT_COLS:
        return 'INTEGER'
    return 'REAL'


def _financial_col_type(col_name):
    """Return SQLite type for financial statement columns."""
    if col_name == 'fiscalDateEnding':
        return 'TEXT NOT NULL'
    if col_name in ('reportedCurrency', 'reportTime', 'reportedDate'):
        return 'TEXT'
    return 'REAL'


def _safe_numeric(value):
    """Convert a string value to int or float, returning None for non-numeric."""
    if value is None or value == 'None' or value == 'none' or value == '' or value == '-':
        return None
    try:
        if '.' in str(value):
            return float(value)
        return int(value)
    except (ValueError, TypeError):
        return None


def create_database():
    """Create the SQLite database with all required tables."""
    os.makedirs(os.path.dirname(investment_db_path()), exist_ok=True)
    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    # ── 1. SEC Tickers table ──────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sec_tickers (
            ticker  TEXT PRIMARY KEY,
            cik     TEXT NOT NULL,
            title   TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sec_tickers_cik ON sec_tickers(cik)")

    # ── 2. Company Details table ──────────────────────────────────────────
    cols_sql = []
    for col in COMPANY_DETAILS_KEYS:
        ctype = _col_type_company_details(col)
        if col == 'Symbol':
            cols_sql.append(f'    "{col}" {ctype} PRIMARY KEY')
        elif col == 'CIK':
            cols_sql.append(f'    "{col}" {ctype}')
        else:
            cols_sql.append(f'    "{col}" {ctype}')
    cols_str = ',\n'.join(cols_sql)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS company_details (
{cols_str}
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_cd_cik ON company_details("CIK")')

    # ── 3. Financial statement tables (annual + quarterly) ────────────────
    def _create_financial_table(table_name, columns):
        col_defs = ['    ticker TEXT NOT NULL']
        for col in columns:
            col_defs.append(f'    "{col}" {_financial_col_type(col)}')
        col_defs.append('    PRIMARY KEY (ticker, "fiscalDateEnding")')
        col_defs.append('    FOREIGN KEY (ticker) REFERENCES sec_tickers(ticker)')
        ddl = f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ',\n'.join(col_defs) + "\n)"
        cur.execute(ddl)

    _create_financial_table('balance_sheet_annual', BALANCE_COLS)
    _create_financial_table('balance_sheet_quarterly', BALANCE_COLS)
    _create_financial_table('cash_flow_annual', CASH_FLOW_COLS)
    _create_financial_table('cash_flow_quarterly', CASH_FLOW_COLS)
    _create_financial_table('income_annual', INCOME_COLS)
    _create_financial_table('income_quarterly', INCOME_COLS)
    _create_financial_table('earnings_annual', EARNINGS_ANNUAL_COLS)
    _create_financial_table('earnings_quarterly', EARNINGS_QUARTERLY_COLS)

    # ── 4. OHLCV tables ──────────────────────────────────────────────────
    ensure_ohlcv_schema(conn)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_meta (
            ticker          TEXT PRIMARY KEY,
            information     TEXT,
            last_refreshed  TEXT,
            output_size     TEXT,
            time_zone       TEXT,
            FOREIGN KEY (ticker) REFERENCES sec_tickers(ticker)
        )
    """)

    # ── 5. Market Capitalization table ─────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_capitalization (
            ticker                TEXT PRIMARY KEY,
            marketCapitalization  REAL,
            marketCapGroup        TEXT,
            FOREIGN KEY (ticker) REFERENCES sec_tickers(ticker)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS magic_formula_symbols (
            ticker         TEXT PRIMARY KEY,
            marketCapGroup TEXT NOT NULL,
            FOREIGN KEY (ticker) REFERENCES sec_tickers(ticker)
        )
    """)

    from Securities_DB.sec_metadata_database import create_sec_metadata_schema

    create_sec_metadata_schema(conn)
    conn.close()


def populate_sec_tickers():
    """Load SEC tickers from company_tickers.json into sec_tickers table."""
    path = os.path.join(get_data_root(), 'company_tickers.json')
    data = load_json_from_file_safe(path)
    if not data:
        print("ERROR: Could not load company_tickers.json")
        return

    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    rows = []
    for key, value in data.items():
        if not key.isnumeric():
            continue
        ticker = value.get('ticker')
        cik_raw = value.get('cik_str')
        title = value.get('title')
        if not ticker or cik_raw is None:
            continue
        # pad CIK to 10 digits
        cik = str(cik_raw).zfill(10)
        rows.append((ticker, cik, title))

    cur.executemany(
        "INSERT OR REPLACE INTO sec_tickers (ticker, cik, title) VALUES (?, ?, ?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"Loaded {len(rows)} tickers into sec_tickers")


def populate_company_details():
    """Load company details from each security's current_company_details.json."""
    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    ts = TickerSearch()
    tickers_data = ts.tickers_titles()
    if not tickers_data:
        print("ERROR: Could not load tickers")
        conn.close()
        return

    sec_dir = os.path.join(get_data_root(), 'Securities')
    count = 0
    skipped = 0

    for key, value in tickers_data.items():
        if not key.isnumeric():
            continue
        ticker = value.get('ticker')
        title = value.get('title')
        cik_raw = value.get('cik_str')
        if not ticker:
            continue

        sub_dir = f"{ticker}__{title}"
        details_path = os.path.join(sec_dir, sub_dir, 'current_company_details.json')

        if not os.path.isfile(details_path):
            skipped += 1
            continue

        data = load_json_from_file_safe(details_path, verbose=False)
        if not data or not isinstance(data, dict):
            skipped += 1
            continue

        # ensure Symbol and CIK are set
        if not data.get('Symbol'):
            data['Symbol'] = ticker
        if not data.get('CIK'):
            data['CIK'] = str(cik_raw).zfill(10)
        else:
            data['CIK'] = str(data['CIK']).zfill(10)
        if not data.get('Name'):
            data['Name'] = title

        # build values list
        vals = []
        for col in COMPANY_DETAILS_KEYS:
            raw = data.get(col)
            if raw is None or raw == 'None' or raw == '' or raw == '-':
                if col in ('Symbol', 'CIK', 'Name'):
                    # these must not be null
                    if col == 'Symbol':
                        vals.append(ticker)
                    elif col == 'CIK':
                        vals.append(str(cik_raw).zfill(10))
                    else:
                        vals.append(title)
                else:
                    vals.append(None)
            elif col in TEXT_COLS or col in DATE_COLS:
                vals.append(str(raw))
            elif col in BIGINT_COLS:
                vals.append(_safe_numeric(raw))
            else:
                vals.append(_safe_numeric(raw))

        placeholders = ', '.join(['?'] * len(COMPANY_DETAILS_KEYS))
        col_names = ', '.join([f'"{c}"' for c in COMPANY_DETAILS_KEYS])
        cur.execute(
            f"INSERT OR REPLACE INTO company_details ({col_names}) VALUES ({placeholders})",
            vals
        )
        count += 1

    conn.commit()
    conn.close()
    print(f"Loaded {count} company details (skipped {skipped})")


def _populate_financial_table(table_name, columns, file_getter):
    """Generic loader for financial statement tables."""
    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    ts = TickerSearch()
    tickers_data = ts.tickers_titles()
    if not tickers_data:
        conn.close()
        return

    sec_dir = os.path.join(get_data_root(), 'Securities')
    count = 0

    for key, value in tickers_data.items():
        if not key.isnumeric():
            continue
        ticker = value.get('ticker')
        title = value.get('title')
        if not ticker:
            continue

        sub_dir = f"{ticker}__{title}"
        file_path = file_getter(sec_dir, sub_dir, ticker)
        if not file_path or not os.path.isfile(file_path):
            continue

        data = load_json_from_file_safe(file_path, verbose=False)
        if not data or not isinstance(data, list):
            continue

        for record in data:
            if not isinstance(record, dict):
                continue
            fiscal_date = record.get('fiscalDateEnding')
            if not fiscal_date:
                continue

            vals = [ticker]
            for col in columns:
                raw = record.get(col)
                if raw is None or raw == 'None' or raw == 'none' or raw == '' or raw == '-':
                    vals.append(None)
                elif col in ('fiscalDateEnding', 'reportedCurrency', 'reportTime', 'reportedDate'):
                    vals.append(str(raw))
                else:
                    vals.append(_safe_numeric(raw))

            col_names = 'ticker, ' + ', '.join([f'"{c}"' for c in columns])
            placeholders = ', '.join(['?'] * (len(columns) + 1))
            try:
                cur.execute(
                    f"INSERT OR REPLACE INTO {table_name} ({col_names}) VALUES ({placeholders})",
                    vals
                )
                count += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    conn.close()
    print(f"Loaded {count} records into {table_name}")


def populate_financial_statements():
    """Load all financial statement data."""
    fin_dir = 'Financial_Statements'

    def balance_annual(sec, sub, tk):
        return os.path.join(sec, sub, fin_dir, 'Balance', 'BalanceAnnualReports.json')

    def balance_quarterly(sec, sub, tk):
        return os.path.join(sec, sub, fin_dir, 'Balance', 'BalanceQuarterlyReports.json')

    def cash_annual(sec, sub, tk):
        return os.path.join(sec, sub, fin_dir, 'Cash_Flow', 'Cash_FlowAnnualReports.json')

    def cash_quarterly(sec, sub, tk):
        return os.path.join(sec, sub, fin_dir, 'Cash_Flow', 'Cash_FlowQuarterlyReports.json')

    def income_annual(sec, sub, tk):
        return os.path.join(sec, sub, fin_dir, 'Income', 'IncomeAnnualReports.json')

    def income_quarterly(sec, sub, tk):
        return os.path.join(sec, sub, fin_dir, 'Income', 'IncomeQuarterlyReports.json')

    def earnings_annual(sec, sub, tk):
        return os.path.join(sec, sub, fin_dir, 'Earnings', 'EarningsAnnualEarnings.json')

    def earnings_quarterly(sec, sub, tk):
        return os.path.join(sec, sub, fin_dir, 'Earnings', 'EarningsQuarterlyEarnings.json')

    print("Loading balance sheets (annual)...")
    _populate_financial_table('balance_sheet_annual', BALANCE_COLS, balance_annual)
    print("Loading balance sheets (quarterly)...")
    _populate_financial_table('balance_sheet_quarterly', BALANCE_COLS, balance_quarterly)
    print("Loading cash flow (annual)...")
    _populate_financial_table('cash_flow_annual', CASH_FLOW_COLS, cash_annual)
    print("Loading cash flow (quarterly)...")
    _populate_financial_table('cash_flow_quarterly', CASH_FLOW_COLS, cash_quarterly)
    print("Loading income statements (annual)...")
    _populate_financial_table('income_annual', INCOME_COLS, income_annual)
    print("Loading income statements (quarterly)...")
    _populate_financial_table('income_quarterly', INCOME_COLS, income_quarterly)
    print("Loading earnings (annual)...")
    _populate_financial_table('earnings_annual', EARNINGS_ANNUAL_COLS, earnings_annual)
    print("Loading earnings (quarterly)...")
    _populate_financial_table('earnings_quarterly', EARNINGS_QUARTERLY_COLS, earnings_quarterly)


def populate_ohlcv():
    """Load OHLCV price history and meta data."""
    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    ts = TickerSearch()
    tickers_data = ts.tickers_titles()
    if not tickers_data:
        conn.close()
        return

    sec_dir = os.path.join(get_data_root(), 'Securities')
    price_count = 0
    meta_count = 0

    for key, value in tickers_data.items():
        if not key.isnumeric():
            continue
        ticker = value.get('ticker')
        title = value.get('title')
        if not ticker:
            continue

        sub_dir = f"{ticker}__{title}"
        ohlcv_dir = os.path.join(sec_dir, sub_dir, 'OHLCV')

        # meta data
        meta_path = os.path.join(ohlcv_dir, f'{ticker}meta.json')
        if os.path.isfile(meta_path):
            meta = load_json_from_file_safe(meta_path, verbose=False)
            if meta and isinstance(meta, dict):
                cur.execute(
                    "INSERT OR REPLACE INTO ohlcv_meta (ticker, information, last_refreshed, output_size, time_zone) VALUES (?, ?, ?, ?, ?)",
                    (
                        ticker,
                        meta.get('1. Information'),
                        meta.get('3. Last Refreshed'),
                        meta.get('4. Output Size'),
                        meta.get('5. Time Zone'),
                    )
                )
                meta_count += 1

        # price history
        ohlcv_path = os.path.join(ohlcv_dir, f'{ticker}ohlcv.json')
        if not os.path.isfile(ohlcv_path):
            continue

        data = load_json_from_file_safe(ohlcv_path, verbose=False)
        if not data or not isinstance(data, dict):
            continue

        price_count += upsert_ohlcv_payload(
            conn,
            ticker,
            data,
            commit=False,
        )

    conn.commit()
    conn.close()
    print(f"Loaded {meta_count} OHLCV meta records, {price_count} daily price records")


def _classify_market_cap(market_cap):
    """Return the market cap category string for a given market cap value."""
    if market_cap is None:
        return None
    if market_cap >= 2e11:
        return 'Mega'
    elif market_cap >= 1e10:
        return 'Large'
    elif market_cap >= 2e9:
        return 'Mid'
    elif market_cap >= 25e7:
        return 'Small'
    elif market_cap >= 1e8:
        return 'Micro'
    return None


def populate_market_capitalization():
    """Populate market_capitalization table using company_details MarketCapitalization."""
    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    cur.execute('SELECT "Symbol", "MarketCapitalization" FROM company_details WHERE "MarketCapitalization" IS NOT NULL')
    rows = cur.fetchall()

    count = 0
    for symbol, mcap in rows:
        try:
            mcap_val = float(mcap)
        except (ValueError, TypeError):
            continue
        group = _classify_market_cap(mcap_val)
        if group is not None:
            cur.execute(
                "INSERT OR REPLACE INTO market_capitalization (ticker, marketCapitalization, marketCapGroup) VALUES (?, ?, ?)",
                (symbol, mcap_val, group)
            )
            count += 1

    conn.commit()
    conn.close()
    print(f"Loaded {count} market capitalization records")


def update_market_capitalization_for_ticker(ticker: str):
    """Update market_capitalization for a single ticker from company_details."""
    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    cur.execute('SELECT "MarketCapitalization" FROM company_details WHERE "Symbol" = ?', (ticker,))
    row = cur.fetchone()
    if row and row[0] is not None:
        try:
            mcap_val = float(row[0])
        except (ValueError, TypeError):
            conn.close()
            return
        group = _classify_market_cap(mcap_val)
        if group is not None:
            cur.execute(
                "INSERT OR REPLACE INTO market_capitalization (ticker, marketCapitalization, marketCapGroup) VALUES (?, ?, ?)",
                (ticker, mcap_val, group)
            )
            print(f"Updated market capitalization for {ticker}: {mcap_val:.0f} ({group})")

    conn.commit()
    conn.close()


def build_full_database():
    """Create and populate the entire database."""
    print("=" * 60)
    print("Investment Securities Database Builder")
    print("=" * 60)

    print("\n[1/6] Creating database schema...")
    create_database()

    print("\n[2/6] Loading SEC tickers...")
    populate_sec_tickers()

    print("\n[3/6] Loading company details...")
    populate_company_details()

    print("\n[4/6] Loading financial statements...")
    populate_financial_statements()

    print("\n[5/6] Loading OHLCV price data...")
    populate_ohlcv()

    print("\n[6/6] Populating market capitalization...")
    populate_market_capitalization()

    from analytics.MyMagicFormula import populate_magic_formula_symbols_table

    print("\n[7/7] Populating Magic Formula symbols...")
    populate_magic_formula_symbols_table()

    print("\n" + "=" * 60)
    print("Database build complete!")
    print(f"Location: {investment_db_path()}")
    print("=" * 60)


def update_ohlcv_for_ticker(ticker: str):
    """Insert or update OHLCV daily prices and meta data for a single ticker from local files."""
    ts = TickerSearch()
    tickers_data = ts.tickers_titles()
    if not tickers_data:
        return

    # find the title for this ticker
    title = None
    for key, value in tickers_data.items():
        if not key.isnumeric():
            continue
        if value.get('ticker') == ticker:
            title = value.get('title')
            break
    if not title:
        print(f"Could not find title for {ticker} in tickers data")
        return

    sec_dir = os.path.join(get_data_root(), 'Securities')
    sub_dir = f"{ticker}__{title}"
    ohlcv_dir = os.path.join(sec_dir, sub_dir, 'OHLCV')

    conn = sqlite3.connect(investment_db_path(), timeout=30)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()
    try:
        cik = None
        for key, value in tickers_data.items():
            if not key.isnumeric():
                continue
            if value.get('ticker') == ticker:
                cik_raw = value.get('cik_str')
                cik = str(cik_raw).zfill(10) if cik_raw is not None else ''
                title = value.get('title') or title
                break
        cur.execute(
            "INSERT OR IGNORE INTO sec_tickers (ticker, cik, title) VALUES (?, ?, ?)",
            (ticker, cik or '', title)
        )

        # meta data
        meta_path = os.path.join(ohlcv_dir, f'{ticker}meta.json')
        if os.path.isfile(meta_path):
            meta = load_json_from_file_safe(meta_path, verbose=False)
            if meta and isinstance(meta, dict):
                cur.execute(
                    "INSERT OR REPLACE INTO ohlcv_meta (ticker, information, last_refreshed, output_size, time_zone) VALUES (?, ?, ?, ?, ?)",
                    (ticker, meta.get('1. Information'), meta.get('3. Last Refreshed'),
                     meta.get('4. Output Size'), meta.get('5. Time Zone'))
                )

        # price history
        ohlcv_path = os.path.join(ohlcv_dir, f'{ticker}ohlcv.json')
        if os.path.isfile(ohlcv_path):
            data = load_json_from_file_safe(ohlcv_path, verbose=False)
            if data and isinstance(data, dict):
                updated_count = upsert_ohlcv_payload(
                    conn,
                    ticker,
                    data,
                    commit=False,
                )
                if updated_count:
                    print(f"Updated {updated_count} OHLCV records for {ticker}")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_company_details_for_ticker(ticker: str):
    """Insert or update company_details for a single ticker from local file."""
    ts = TickerSearch()
    tickers_data = ts.tickers_titles()
    if not tickers_data:
        return

    title = None
    for key, value in tickers_data.items():
        if not key.isnumeric():
            continue
        if value.get('ticker') == ticker:
            title = value.get('title')
            break
    if not title:
        print(f"Could not find title for {ticker} in tickers data")
        return

    sec_dir = os.path.join(get_data_root(), 'Securities')
    sub_dir = f"{ticker}__{title}"
    cd_path = os.path.join(sec_dir, sub_dir, 'current_company_details.json')

    if not os.path.isfile(cd_path):
        print(f"No company details file for {ticker}")
        return

    data = load_json_from_file_safe(cd_path, verbose=False)
    if not data or not isinstance(data, dict):
        return

    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    vals = []
    for col in COMPANY_DETAILS_KEYS:
        raw = data.get(col)
        if raw is None or raw == 'None' or raw == 'none' or raw == '' or raw == '-':
            vals.append(None)
        elif col in TEXT_COLS:
            vals.append(str(raw))
        elif col in DATE_COLS:
            vals.append(str(raw))
        elif col in BIGINT_COLS:
            vals.append(_safe_numeric(raw))
        else:
            vals.append(_safe_numeric(raw))

    col_names = ', '.join([f'"{c}"' for c in COMPANY_DETAILS_KEYS])
    placeholders = ', '.join(['?'] * len(COMPANY_DETAILS_KEYS))
    cur.execute(
        f"INSERT OR REPLACE INTO company_details ({col_names}) VALUES ({placeholders})",
        vals
    )

    conn.commit()
    conn.close()
    print(f"Updated company details for {ticker}")


def update_financial_table_for_ticker(ticker: str, table_name: str, columns: list, file_path: str):
    """Insert or update a single financial statement table for a ticker from a local file."""
    if not os.path.isfile(file_path):
        print(f"No file at {file_path}")
        return

    data = load_json_from_file_safe(file_path, verbose=False)
    if not data or not isinstance(data, list):
        return

    conn = sqlite3.connect(investment_db_path())
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()
    count = 0

    for record in data:
        if not isinstance(record, dict):
            continue
        fiscal_date = record.get('fiscalDateEnding')
        if not fiscal_date:
            continue

        vals = [ticker]
        for col in columns:
            raw = record.get(col)
            if raw is None or raw == 'None' or raw == 'none' or raw == '' or raw == '-':
                vals.append(None)
            elif col in ('fiscalDateEnding', 'reportedCurrency', 'reportTime', 'reportedDate'):
                vals.append(str(raw))
            else:
                vals.append(_safe_numeric(raw))

        col_names = 'ticker, ' + ', '.join([f'"{c}"' for c in columns])
        placeholders = ', '.join(['?'] * (len(columns) + 1))
        try:
            cur.execute(
                f"INSERT OR REPLACE INTO {table_name} ({col_names}) VALUES ({placeholders})",
                vals
            )
            count += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print(f"Updated {count} records in {table_name} for {ticker}")


def update_financials_for_ticker(ticker: str):
    """Update all financial statement tables for a single ticker from local files."""
    ts = TickerSearch()
    tickers_data = ts.tickers_titles()
    if not tickers_data:
        return

    title = None
    for key, value in tickers_data.items():
        if not key.isnumeric():
            continue
        if value.get('ticker') == ticker:
            title = value.get('title')
            break
    if not title:
        print(f"Could not find title for {ticker} in tickers data")
        return

    sec_dir = os.path.join(get_data_root(), 'Securities')
    sub_dir = f"{ticker}__{title}"
    fin_dir = os.path.join(sec_dir, sub_dir, 'Financial_Statements')

    table_map = [
        ('balance_sheet_annual', BALANCE_COLS, os.path.join(fin_dir, 'Balance', 'BalanceAnnualReports.json')),
        ('balance_sheet_quarterly', BALANCE_COLS, os.path.join(fin_dir, 'Balance', 'BalanceQuarterlyReports.json')),
        ('cash_flow_annual', CASH_FLOW_COLS, os.path.join(fin_dir, 'Cash_Flow', 'Cash_FlowAnnualReports.json')),
        ('cash_flow_quarterly', CASH_FLOW_COLS, os.path.join(fin_dir, 'Cash_Flow', 'Cash_FlowQuarterlyReports.json')),
        ('income_annual', INCOME_COLS, os.path.join(fin_dir, 'Income', 'IncomeAnnualReports.json')),
        ('income_quarterly', INCOME_COLS, os.path.join(fin_dir, 'Income', 'IncomeQuarterlyReports.json')),
        ('earnings_annual', EARNINGS_ANNUAL_COLS, os.path.join(fin_dir, 'Earnings', 'EarningsAnnualEarnings.json')),
        ('earnings_quarterly', EARNINGS_QUARTERLY_COLS, os.path.join(fin_dir, 'Earnings', 'EarningsQuarterlyEarnings.json')),
    ]

    for table_name, columns, file_path in table_map:
        update_financial_table_for_ticker(ticker, table_name, columns, file_path)


if __name__ == '__main__':
    build_full_database()
