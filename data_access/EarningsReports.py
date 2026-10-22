# Python 3.14
# created: May 13, 2026
# Intermediary class between the earnings report database tables and analysis classes

import pandas as pd
from Securities_DB.db_connection import get_connection
from data_access.date_selection import select_statement_date


class EarningsReports:
    """
    Provides access to earnings_annual and earnings_quarterly tables.
    Acts as the intermediary between the database and the analysis Classes files.
    """

    def __init__(self, ticker: str):
        if not isinstance(ticker, str):
            raise ValueError("ticker must be a string")
        self.ticker = ticker if ticker.isupper() else ticker.upper()


    @staticmethod
    def _safe_dict(row) -> dict:
        if row is None:
            return {}
        if isinstance(row, dict):
            return row
        return dict(row)


    def annual(self) -> pd.DataFrame:
        """Return annual earnings data for the ticker as a DataFrame."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM earnings_annual WHERE ticker = ? ORDER BY "fiscalDateEnding" DESC',
            conn, params=(self.ticker,)
        )
        conn.close()
        idx_len = len(df.index)
        for idx in range(idx_len-2):
            df.loc[idx,'eps3YrAvg'] = df.reportedEPS[idx:idx+3].mean()

        return df


    def quarterly(self) -> pd.DataFrame:
        """Return quarterly earnings data for the ticker as a DataFrame."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM earnings_quarterly WHERE ticker = ? ORDER BY "fiscalDateEnding" DESC',
            conn, params=(self.ticker,)
        )
        conn.close()
        df['reportedEPS'] = pd.to_numeric(df.get('reportedEPS'), errors='coerce')
        df['epsTTM'] = pd.NA
        for idx in range(max(0, len(df.index) - 3)):
            df.loc[idx, 'epsTTM'] = df['reportedEPS'].iloc[idx:idx + 4].sum(
                min_count=4
            )
        df['epsTTM'] = pd.to_numeric(df['epsTTM'], errors='coerce')

        return df


    def latest_annual(self) -> dict:
        """Return the most recent annual earnings as a dictionary."""
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT * FROM earnings_annual WHERE ticker = ? ORDER BY "fiscalDateEnding" DESC LIMIT 1',
            (self.ticker,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None


    def latest_quarterly(self) -> dict:
        """Return the most recent quarterly earnings as a dictionary."""
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT * FROM earnings_quarterly WHERE ticker = ? ORDER BY "fiscalDateEnding" DESC LIMIT 1',
            (self.ticker,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None


    def get_by_date(self, fiscal_date: str, quarterly: bool = False) -> dict:
        """Return earnings report for a specific fiscal date."""
        fiscal_date = self.get_closest_date(fiscal_date, quarterly=quarterly)
        table = 'earnings_quarterly' if quarterly else 'earnings_annual'
        conn = get_connection(readonly=True)
        try:
            row = conn.execute(
                f'SELECT * FROM {table} WHERE ticker = ? AND "fiscalDateEnding" = ? LIMIT 1',
                (self.ticker, fiscal_date)
            ).fetchone()
        finally:
            conn.close()
        return self._safe_dict(row) if row else None

    def get_closest_date(self,date:str|None=None, quarterly: bool = False):
        table = 'earnings_quarterly' if quarterly else 'earnings_annual'
        conn = get_connection(readonly=True)
        try:
            dt_dates = pd.read_sql_query(
                f"SELECT fiscalDateEnding FROM {table} WHERE ticker = ?",
                conn,
                params=(self.ticker,)
            )
        finally:
            conn.close()
        return select_statement_date(
            dt_dates.fiscalDateEnding,
            date,
            quarterly=quarterly,
        )
