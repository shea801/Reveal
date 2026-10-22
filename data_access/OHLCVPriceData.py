# Python 3.14
# created: May 13, 2026
# Intermediary class between the OHLCV price database tables and analysis classes

import pandas as pd
import datetime as dt

from Securities_DB.db_connection import get_connection


class OHLCVPriceData:
    """
    Provides access to ohlcv_daily and ohlcv_meta tables.
    Acts as the intermediary between the database and the analysis Classes files
    used to analyze the price data.
    """

    def __init__(self, ticker: str):
        if not isinstance(ticker, str):
            raise TypeError("ticker must be a string")
        self.ticker = ticker.upper()

    def daily_prices(self) -> pd.DataFrame:
        """Return full daily OHLCV price history as a DataFrame."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM ohlcv_daily WHERE ticker = ? ORDER BY date DESC',
            conn, params=(self.ticker,)
        )
        conn.close()
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df

    def price_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Return OHLCV data between start_date and end_date (inclusive, YYYY-MM-DD)."""
        # normalize start and end dates to dates that have records
        start_dt = self.get_closest_date(start_date)
        end_dt = self.get_closest_date(end_date)

        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')

        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT * FROM ohlcv_daily WHERE ticker = ? AND date >= ? AND date <= ? ORDER BY date',
            conn, params=(self.ticker, start_date, end_date)
        )
        conn.close()
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df

    def price_on_date(self, date: str) -> dict | None:
        """Return OHLCV data for a specific date."""
        date = self.get_closest_date(date)
        date = date.strftime('%Y-%m-%d')

        conn = get_connection(readonly=True)
        rows = conn.execute(
            'SELECT * FROM ohlcv_daily WHERE ticker = ?',
            (self.ticker,)
        ).fetchall()
        rows = [dict(r) for r in rows]
        conn.close()
        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'])
        if date not in df.date.dt.strftime('%Y-%m-%d').tolist():
            return None

        return df[df.date.dt.strftime('%Y-%m-%d') == date].iloc[0].to_dict()

    def latest_price(self) -> dict | None:
        """Return the most recent OHLCV record."""
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT * FROM ohlcv_daily WHERE ticker = ? ORDER BY date DESC LIMIT 1',
            (self.ticker,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def meta(self) -> dict | None:
        """Return the OHLCV meta data (symbol, last refreshed, timezone, etc.)."""
        conn = get_connection(readonly=True)
        row = conn.execute(
            'SELECT * FROM ohlcv_meta WHERE ticker = ?',
            (self.ticker,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def closing_prices(self) -> pd.DataFrame:
        """Return date and close price only, useful for charting and moving averages."""
        conn = get_connection(readonly=True)
        df = pd.read_sql_query(
            'SELECT date, close FROM ohlcv_daily WHERE ticker = ? ORDER BY date',
            conn, params=(self.ticker,)
        )
        conn.close()
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        return df

    def adjusted_closing_prices(self) -> pd.DataFrame:
        """Return split/dividend-adjusted closes for total-return workflows."""
        conn = get_connection(readonly=True)
        try:
            df = pd.read_sql_query(
                """
                SELECT date, adjusted_close
                FROM ohlcv_daily
                WHERE ticker = ? AND adjusted_close IS NOT NULL
                ORDER BY date
                """,
                conn,
                params=(self.ticker,),
            )
        finally:
            conn.close()
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        return df

    def dividend_history(self) -> pd.DataFrame:
        """Return daily dividend events and explicit zero-payment records."""
        conn = get_connection(readonly=True)
        try:
            df = pd.read_sql_query(
                """
                SELECT date, dividend_amount, price_source
                FROM ohlcv_daily
                WHERE ticker = ?
                ORDER BY date
                """,
                conn,
                params=(self.ticker,),
            )
        finally:
            conn.close()
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["dividend_amount"] = pd.to_numeric(
                df["dividend_amount"],
                errors="coerce",
            )
        return df

    def adjusted_price_on_date(self, date: str) -> dict | None:
        """Return an exact adjusted-price row without date substitution."""
        try:
            normalized = dt.date.fromisoformat(str(date)).isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError("date must be in ISO format YYYY-MM-DD") from exc
        conn = get_connection(readonly=True)
        try:
            row = conn.execute(
                """
                SELECT ticker, date, close, adjusted_close, dividend_amount,
                       split_coefficient, price_source
                FROM ohlcv_daily
                WHERE ticker = ? AND date = ?
                  AND adjusted_close IS NOT NULL
                LIMIT 1
                """,
                (self.ticker, normalized),
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None


    def get_closest_date(self, date: str | None = None) -> dt.datetime:
        """
        Return the latest trading date on or before ``date``.

        A date before the available price history raises ``ValueError`` rather
        than returning a future price, which would introduce look-ahead bias.
        When ``date`` is omitted, the latest available trading date is returned.
        """
        if date is None:
            latest = self.latest_price()
            if not latest or not latest.get('date'):
                raise ValueError(
                    f"Input date not provided, and no date found in price data for {self.ticker}."
                )
            date = latest['date']

        try:
            requested_date = pd.to_datetime(date)
        except (TypeError, ValueError) as exc:
            raise ValueError("date must be in ISO format YYYY-MM-DD") from exc

        prices = self.closing_prices()
        if prices.empty:
            raise ValueError(f"No date found in price data for {self.ticker}.")

        available_dates = pd.DatetimeIndex(prices.index).dropna().sort_values()
        prior_dates = available_dates[available_dates <= requested_date]
        if prior_dates.empty:
            raise ValueError(
                f"No price data for {self.ticker} on or before "
                f"{requested_date.strftime('%Y-%m-%d')}."
            )

        selected_date = prior_dates[-1]
        return selected_date.to_pydatetime()
