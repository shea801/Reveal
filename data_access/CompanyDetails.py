# Python 3.14
# created: May 13, 2026
# Intermediary class between the company_details database table and analysis classes

import pandas as pd

from Securities_DB.db_connection import get_connection


class CompanyDetails:
    """
    Provides access to the company_details table in the investment database.
    Acts as the intermediary between the database and the analysis Classes files.
    """

    def __init__(self, ticker:str = None):
        self.ticker = ticker.upper() if ticker else None

    @staticmethod
    def _safe_dict(row) -> dict:
        if row is None:
            return {}
        if isinstance(row, dict):
            return row
        return dict(row)

    def get_details(self, ticker: str = None) -> dict:
        """Return a single security's company details as a dictionary."""
        tk = (ticker or self.ticker)
        if not tk:
            return {}
        tk = tk.upper()
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT * FROM company_details WHERE "Symbol" = ?', (tk,)
        ).fetchone()
        conn.close()
        return self._safe_dict(row)

    def get_details_df(self, ticker: str = None) -> pd.DataFrame:
        """Return a single security's company details as a single-row DataFrame."""
        tk = (ticker or self.ticker)
        if not tk:
            return pd.DataFrame()
        tk = tk.upper()
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM company_details WHERE "Symbol" = ?', conn, params=(tk,)
        )
        conn.close()
        return df

    def get_all(self) -> pd.DataFrame:
        """Return all company details as a DataFrame."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query('SELECT * FROM company_details', conn)
        conn.close()
        return df

    def get_peer_metadata(self) -> pd.DataFrame:
        """Return only persisted fields used to define comparison cohorts."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            '''
            SELECT
                "Symbol",
                "Name",
                "AssetType",
                "Exchange",
                "MarketCapitalization",
                "Sector",
                "Industry"
            FROM company_details
            ''',
            conn,
        )
        conn.close()
        return df

    def search_by_sector(self, sector: str) -> pd.DataFrame:
        """Return all securities in a given sector."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM company_details WHERE "Sector" = ?', conn, params=(sector,)
        )
        conn.close()
        return df

    def search_by_industry(self, industry: str) -> pd.DataFrame:
        """Return all securities in a given industry."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM company_details WHERE "Industry" = ?', conn, params=(industry,)
        )
        conn.close()
        return df

    def search_by_asset_type(self, asset_type: str) -> pd.DataFrame:
        """Return all securities of a given asset type."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM company_details WHERE "AssetType" = ?', conn, params=(asset_type,)
        )
        conn.close()
        return df

    def revenue_filter(self, min_revenue: float = 1e8) -> pd.DataFrame:
        """Return securities with TTM revenue >= min_revenue (default $100M)."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM company_details WHERE "RevenueTTM" >= ?', conn, params=(min_revenue,)
        )
        conn.close()
        return df

    def get_sec_ticker_info(self, ticker: str = None) -> dict:
        """Return the SEC ticker record (ticker, cik, title) from sec_tickers table."""
        tk = (ticker or self.ticker)
        if not tk:
            return {}
        tk = tk.upper()
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT * FROM sec_tickers WHERE ticker = ?', (tk,)
        ).fetchone()
        conn.close()
        return self._safe_dict(row)

    def all_sec_tickers(self) -> pd.DataFrame:
        """Return the full sec_tickers table as a DataFrame."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query('SELECT * FROM sec_tickers', conn)
        conn.close()
        return df

    def company_names_for_tickers(self, tickers) -> dict[str, str]:
        """Return persisted company names for a collection of ticker symbols."""
        normalized_tickers = sorted({
            str(ticker).strip().upper()
            for ticker in tickers
            if str(ticker).strip()
        })
        if not normalized_tickers:
            return {}

        names: dict[str, str] = {}
        conn = get_connection(readonly=True)
        try:
            for start in range(0, len(normalized_tickers), 400):
                batch = normalized_tickers[start:start + 400]
                placeholders = ", ".join("?" for _ in batch)
                sec_rows = conn.execute(
                    f"""
                    SELECT UPPER(ticker) AS ticker, title
                    FROM sec_tickers
                    WHERE UPPER(ticker) IN ({placeholders})
                    """,
                    batch,
                ).fetchall()
                for row in sec_rows:
                    name = str(row["title"] or "").strip()
                    if name:
                        names[row["ticker"]] = name

                detail_rows = conn.execute(
                    f"""
                    SELECT UPPER("Symbol") AS ticker, "Name" AS company_name
                    FROM company_details
                    WHERE UPPER("Symbol") IN ({placeholders})
                    """,
                    batch,
                ).fetchall()
                for row in detail_rows:
                    name = str(row["company_name"] or "").strip()
                    if name:
                        names[row["ticker"]] = name
        finally:
            conn.close()
        return names

    @staticmethod
    def _cik_search_values(query: str) -> tuple[str, str]:
        value = query.strip()
        if value.upper().startswith("CIK"):
            value = value[3:].lstrip(" #:.-")
        if not value.isdigit() or len(value) > 10:
            return "", ""
        return value.zfill(10), value

    @staticmethod
    def _escape_like(value: str) -> str:
        return (
            value.replace("!", "!!")
            .replace("%", "!%")
            .replace("_", "!_")
        )

    def search_sec_tickers(
        self,
        query: str,
        limit: int = 8,
    ) -> list[dict]:
        """Search SEC ticker metadata by ticker, CIK, or company title."""
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return []
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")

        limit = min(limit, 50)
        query_upper = normalized_query.upper()
        escaped_query = self._escape_like(query_upper)
        contains_pattern = f"%{escaped_query}%"
        prefix_pattern = f"{escaped_query}%"
        exact_cik, cik_fragment = self._cik_search_values(normalized_query)
        cik_pattern = f"%{cik_fragment}%" if cik_fragment else ""

        conn = get_connection(readonly=True)
        try:
            rows = conn.execute(
                """
                SELECT ticker, cik, title
                FROM sec_tickers
                WHERE UPPER(ticker) LIKE ? ESCAPE '!'
                   OR UPPER(COALESCE(title, '')) LIKE ? ESCAPE '!'
                   OR (
                        ? <> ''
                        AND (cik = ? OR cik LIKE ?)
                   )
                ORDER BY
                    CASE
                        WHEN UPPER(ticker) = ? THEN 0
                        WHEN ? <> '' AND cik = ? THEN 1
                        WHEN UPPER(COALESCE(title, '')) = ? THEN 2
                        WHEN UPPER(ticker) LIKE ? ESCAPE '!' THEN 3
                        WHEN UPPER(COALESCE(title, '')) LIKE ? ESCAPE '!' THEN 4
                        ELSE 5
                    END,
                    LENGTH(COALESCE(title, '')),
                    UPPER(COALESCE(title, '')),
                    UPPER(ticker)
                LIMIT ?
                """,
                (
                    contains_pattern,
                    contains_pattern,
                    exact_cik,
                    exact_cik,
                    cik_pattern,
                    query_upper,
                    exact_cik,
                    exact_cik,
                    query_upper,
                    prefix_pattern,
                    prefix_pattern,
                    limit,
                ),
            ).fetchall()
            return [self._safe_dict(row) for row in rows]
        finally:
            conn.close()

    def get_fiscal_year_end(self, ticker: str = None) -> str | None:
        """Return the FiscalYearEnd month name (e.g. 'December') for the ticker."""
        details = self.get_details(ticker)
        if not details:
            return None
        return details.get('FiscalYearEnd')

    def get_latest_quarter(self, ticker: str = None) -> str | None:
        """Return the LatestQuarter date string (YYYY-MM-DD) for the ticker."""
        details = self.get_details(ticker)
        if not details:
            return None
        return details.get('LatestQuarter')

    def get_latest_quarterly_fiscal_date(self, ticker: str = None) -> str | None:
        """Return the most recent fiscalDateEnding from quarterly income statements in the DB."""
        tk = (ticker or self.ticker)
        if not tk:
            return None
        tk = tk.upper()
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT "fiscalDateEnding" FROM income_quarterly WHERE ticker = ? '
            'ORDER BY "fiscalDateEnding" DESC LIMIT 1',
            (tk,)
        ).fetchone()
        conn.close()
        return row['fiscalDateEnding'] if row else None

    def get_latest_annual_fiscal_date(self, ticker: str = None) -> str | None:
        """Return the most recent fiscalDateEnding from annual income statements in the DB."""
        tk = (ticker or self.ticker)
        if not tk:
            return None
        tk = tk.upper()
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT "fiscalDateEnding" FROM income_annual WHERE ticker = ? '
            'ORDER BY "fiscalDateEnding" DESC LIMIT 1',
            (tk,)
        ).fetchone()
        conn.close()
        return row['fiscalDateEnding'] if row else None
