# Python 3.14
# created: May 13, 2026
# Intermediary class between the income statement database tables and analysis classes

import pandas as pd

from Securities_DB.db_connection import get_connection
from data_access.date_selection import select_statement_date


class IncomeStatements:
    """
    Provides access to income_annual and income_quarterly tables.
    Acts as the intermediary between the database and the analysis Classes files.
    """

    def __init__(self, ticker: str):
        if not isinstance(ticker, str):
            raise TypeError("ticker must be a string")
        self.ticker = ticker if ticker.isupper() else ticker.upper()

    @staticmethod
    def _safe_dict(row) -> dict:
        if row is None:
            return {}
        if isinstance(row, dict):
            return row
        return dict(row)


    def annual(self) -> pd.DataFrame:
        """Return annual income statement data for the ticker as a DataFrame."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM income_annual WHERE ticker = ? ORDER BY "fiscalDateEnding" DESC',
            conn, params=(self.ticker,)
        )
        conn.close()
        return df


    def quarterly(self) -> pd.DataFrame:
        """Return quarterly income statements as a DataFrame."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM income_quarterly WHERE ticker = ? ORDER BY "fiscalDateEnding" DESC',
            conn, params=(self.ticker,)
        )
        conn.close()
        return df


    def latest_annual(self) -> dict:
        """Return the most recent annual income statement as a dictionary."""
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT * FROM income_annual WHERE ticker = ? ORDER BY "fiscalDateEnding" DESC LIMIT 1',
            (self.ticker,)
        ).fetchone()
        conn.close()
        return self._safe_dict(row)


    def latest_quarterly(self) -> dict:
        """Return the most recent quarterly income statement as a dictionary."""
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT * FROM income_quarterly WHERE ticker = ? ORDER BY "fiscalDateEnding" DESC LIMIT 1',
            (self.ticker,)
        ).fetchone()
        conn.close()
        return self._safe_dict(row)


    def get_by_date(self, fiscal_date: str, quarterly: bool = False) -> dict:
        """Return income statement for a specific fiscal date."""
        fiscal_date = self.get_closest_date(fiscal_date, quarterly=quarterly)
        table = 'income_quarterly' if quarterly else 'income_annual'
        conn = get_connection(readonly=True)
        try:
            row = conn.execute(
                f'SELECT * FROM {table} WHERE ticker = ? AND "fiscalDateEnding" = ? LIMIT 1',
                (self.ticker, fiscal_date)
            ).fetchone()
        finally:
            conn.close()
        return self._safe_dict(row) if row else None


    def get_closest_date(self, date: str | None = None, quarterly: bool = False):
        table = 'income_quarterly' if quarterly else 'income_annual'
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
