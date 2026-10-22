# python 3.14

import pandas as pd
import numpy as np
import os
import json
import datetime as dt


"""
This file's purpose is to hold the functions and classes needed to create the various
types of dataframes and tables needed in order to categorize and store the data from
each security.
"""

# US GAAP taxonomy labels needed ( or possibly needed ) for calculations
GAAP_labels = (
    'totalAssets', 'totalCurrentAssets', 'intangibleAssets', 'longTermDebt', 'shortTermDebt', 'ebit',
    'ebitda', 'commonStockSharesOutstanding', 'close', 'reportedEPS', 'totalLiabilities',
    'paymentsForRepurchaseOfPreferredStock', 'shortLongTermDebtTotal', 'totalNonCurrentAssets'
)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


# used to transform the data types in each column of a dataframe
def transform_type(value:str):
    """
    This function will return the data type for each value w/in the dataframe.
    This function can then be used to determine which datatype to assign that particular
    column. The data values are type string (from the SEC filing schema)
    """
    neg = False
    if not isinstance(value,str):
        raise ValueError("Argument must be a string")
    if value.startswith('-'):
        value = value.strip('-')
        neg = True
    if value.isnumeric():
       t = int(value) if not neg else int(value) * -1
    elif '.' in value:
        vsplt = value.split('.')
        if len(vsplt) == 2:
            if vsplt[0].isnumeric() and vsplt[1].isnumeric():
                t = float(value) if not neg else float(value) * -1
            elif vsplt[0].isnumeric() and vsplt[1] == '':
                t = float(value) if not neg else float(value) * -1
            elif vsplt[0] == '' and vsplt[1].isnumeric():
                t = float(value) if not neg else float(value) * -1
            else:
                t = str(value) if not neg else '-' + str(value)
        else:
            t = str(value) if not neg else '-' + str(value)
    else:
        t = str(value) if not neg else '-' + str(value)

    return t

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def transform_dataframe_dtypes(df):
    # Transform the data within the dataframe to the appropriate data type
    try:
        df = df.copy()
    except ValueError as ve:
        print(ve)
    # for deprecation warning in pandas
    pd.set_option('future.no_silent_downcasting', True)

    for col in df.columns:
        if col == 'fiscalDateEnding':
            # Convert date columns to datetime
            df['fiscalDateEnding'] = pd.to_datetime(df.loc[:, 'fiscalDateEnding'], errors='coerce')
        elif col not in ['reportedCurrency']:
            # Replace string 'None' with actual None/NaN before conversion
            if df[col].dtype == 'object':
                df.loc[:,col] = df.loc[:,col].replace(
                    to_replace=['None', 'none', 'null', 'NULL'],
                    value=np.nan)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class FinancialStatementsFromFile:
    """
    FinancialStatementDataExtracting class will retrieve data for either the annual` financial statements.
    Methods will be company_details, income_statement(), cash_flow(), balance_sheet(), and earnings_report().
    and the OHLCV weekly data. (I amy still change the OHLCV from weekly to something else. I don't need daily
    prince checks. Generally, you simply need either the current share price, or a historical one from a specific
    date.
    """

    def __init__(self,ticker:str):
        """
        Initializes the FinancialStatementsFromFile class with a ticker symbol.

        Parameters:
            ticker (str): The ticker symbol of the company for which financial data is to be extracted.
        """
        # Suppress the Deprecation warning in Pandas for using 'replace'. The method used is current.
        # for deprecation warning in pandas
        pd.set_option('future.no_silent_downcasting', True)

        from data_ingestion.TickerFileSearch import TickerSearch as TS

        if not isinstance(ticker, str):
            raise TypeError("symbol must be a string")

        # bring in the TickerSearch class to help find securities information
        ts = TS()
        ticker = ticker if ticker.isupper() else ticker.upper()
        ticker_path = ts.ticker_file_pathways(ticker)
        has_data = ts.ticker_data_present(ticker)
        ticker_search_path = ticker_path.get('ticker_search')

        # verify there is information to extract
        if not all(has_data.values()):
            raise ValueError(f"{ticker} has no valid ticker data...")

        if not isinstance(ticker_path, dict):
            raise ValueError(f"{ticker} has no valid file path mapping.")

        if not isinstance(ticker_search_path, str) or ticker_search_path == '':
            raise ValueError(f"{ticker} has no ticker search file/path metadata...")

        keys = [
            key for key, value in ticker_path.items()
            if key not in {'', '.'}
               and value not in (None, False, '')
               and has_data.get(key, False)
        ]

        if not keys:
            raise KeyError(f"{ticker} has no data.")

        object.__setattr__(self, 'ticker', ticker)
        object.__setattr__(self, 'ts', ts)
        object.__setattr__(self, 'ticker_path', ticker_path)
        object.__setattr__(self, 'ticker_search_path', ticker_search_path)
        object.__setattr__(self, 'keys', keys)


    def _get_annual_path(self, key: str):
        path_value = self.ticker_path.get(key)

        if isinstance(path_value, dict) and len(path_value) > 0:
            annual_path = path_value.get('annual')
        elif isinstance(path_value, str):
            annual_path = path_value
        else:
            return None

        if not isinstance(annual_path, str) or annual_path == '':
            return None

        if not os.path.exists(annual_path):
            return None

        return annual_path


    def _get_quarterly_path(self, key: str):
        path_value = self.ticker_path.get(key)

        if isinstance(path_value, dict) and len(path_value) > 0:
            quarterly_path = path_value.get('quarterly')
        elif isinstance(path_value, str):
            quarterly_path = path_value
        else:
            return None

        if not isinstance(quarterly_path, str) or quarterly_path == '':
            return None

        if not os.path.exists(quarterly_path):
            return None

        return quarterly_path


    def company_details(self):
        """
        company_details will retrieve the data from the respective file which has all the current
        company details including, ticker symbol company name/address/website/region/currency/profile.
        It will also hold the CURRENT (it is NOT considered to be hard fact reported by the company. Company
        details are like quarterly reports. They aren't required to be audited and held to the standard of
        an annual report. The information may be more forecasting ('speculation'(?)) than financially accurate.
        """
        ticker = self.ticker
        if 'company_details' not in self.keys:
            raise KeyError(f"{ticker} has no company details.")
            return None
        co_path = self.ticker_path.get('company_details')

        if co_path is None:
            raise KeyError(f"{ticker} has no company details.")
            return None

        with open(co_path,'r') as f:
            cd_data = json.load(f)

        cddf = pd.DataFrame.from_dict(cd_data,orient='index')

        return cddf


    def income_statement(self,quarterly=False):
        """
        income_statement will retrieve annual data for the Income Statements.
        """
        ticker = self.ticker
        if 'income' not in self.keys:
            raise KeyError(f"{ticker} has no income statement data.")
            return None

        if quarterly:
            income_statement = self._get_quarterly_path('income')
        else:
            income_statement = self._get_annual_path('income')
        if income_statement is None:
            raise KeyError(f"{ticker} has no income statement data.")
            return None

        with open(income_statement, 'r') as f:
            inc_data = json.load(f)
            idf = pd.DataFrame(inc_data)
        # create datetime index
        idf.index = pd.DatetimeIndex(idf.fiscalDateEnding)
        idf.drop('fiscalDateEnding', axis=1, inplace=True)

        return transform_dataframe_dtypes(idf)


    def cash_flow(self,quarterly=False):
        """
        cash_flow will retrieve annual data for the Cash Flows.
        """
        ticker = self.ticker
        if 'cash' not in self.keys:
            raise KeyError(f"{ticker} has no cash flow data.")
            return None

        if quarterly:
            cash_flow = self._get_quarterly_path('cash')
        else:
            cash_flow = self._get_annual_path('cash')

        if cash_flow is None:
            raise KeyError(f"{ticker} has no cash flow data.")
            return None

        with open(cash_flow, 'r') as f:
            cf_data = json.load(f)

        cfdf = pd.DataFrame(cf_data)
        # create datetime index
        cfdf.index = pd.DatetimeIndex(cfdf.fiscalDateEnding)
        cfdf.drop('fiscalDateEnding', axis=1, inplace=True)

        return transform_dataframe_dtypes(cfdf)


    def balance_sheet(self,quarterly=False):
        """
        balance_sheet will retrieve annual data for the Balance Sheets.
        """
        ticker = self.ticker
        keys = self.keys
        if 'balance' not in keys:
            raise KeyError(f"{ticker} has no balance sheet data.")
            return None

        if quarterly:
            balance_sheet = self._get_quarterly_path('balance')
        else:
            balance_sheet = self._get_annual_path('balance')

        if balance_sheet is None:
            raise KeyError(f"{ticker} has no balance sheet data.")
            return None

        with open(balance_sheet, 'r') as f:
            bal_data = json.load(f)

        baldf = pd.DataFrame(bal_data)
        # create datetime index
        baldf.index = pd.DatetimeIndex(baldf.fiscalDateEnding)
        baldf.drop('fiscalDateEnding', axis=1, inplace=True)

        return transform_dataframe_dtypes(baldf)


    def earnings_report(self,quarterly=False):
        """
        Earnings Report retrieves annual data for the Earnings Reports.
        """
        ticker = self.ticker
        keys = self.keys
        if 'earnings' not in keys:
            raise KeyError(f"{ticker} has no earnings report data.")
            return None

        if quarterly:
            earnings_report = self._get_annual_path('earnings')
        else:
            earnings_report = self._get_annual_path('earnings')

        if earnings_report is None:
            raise KeyError(f"{ticker} has no earnings report data.")
            return None

        with open(earnings_report, 'r') as f:
            earn_data = json.load(f)
        edf = pd.DataFrame(earn_data)
        # create datetime index
        edf.index = pd.DatetimeIndex(edf.fiscalDateEnding)
        edf.drop('fiscalDateEnding', axis=1, inplace=True)

        return transform_dataframe_dtypes(edf)


    def ohlcv(self,):
        """
        Retrieves the data related to OHLCV (Open, High, Low, Close, Volume) history.
        """
        ticker = self.ticker
        keys = self.keys
        if 'ohlcv' not in keys:
            raise KeyError(f"{ticker} does not have OHLCV data.")
            return None

        ohlcv_path = self.ticker_path.get('ohlcv')['price_hx']

        if ohlcv_path is None:
            raise KeyError(f"{ticker} does not have OHLCV data.")
            return None

        with open(ohlcv_path, 'r') as f:
            ohlcv_data = json.load(f)

        df = pd.DataFrame(ohlcv_data.values(),index=ohlcv_data.keys())
        # keys::= 'N. [open|high|low|close|volume]'
        cols = [c.split('.')[1].strip() for c in df.columns]
        # rename the columns
        df.rename(columns=dict(zip(df.columns, cols)), inplace=True)
        # convert data types
        df = transform_dataframe_dtypes(df)
        # set fiscalDateEnding columns
        df.index = pd.DatetimeIndex(df.index)

        return transform_dataframe_dtypes(df)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class FinancialData:
    """
    data_frame creator for the financial data of a given security (ticker symbol).
    """
    def __init__(self,
                 ticker:str,
                 balance:pd.DataFrame | None = None,
                 cash:pd.DataFrame | None = None,
                 income:pd.DataFrame | None = None,
                 earnings:pd.DataFrame | None = None,
                 company_details:pd.DataFrame | None = None,
                 ohlcv:pd.DataFrame | None = None,
                 ):
        if not isinstance(ticker,str):
            raise TypeError("ticker must be a string")
        ticker = ticker if ticker.isupper() else ticker.upper()

        # for deprecation warning in pandas
        pd.set_option('future.no_silent_downcasting', True)
        # verify the ticker symbol is valid
        from data_ingestion.TickerFileSearch import TickerSearch as TS
        from Securities_DB.db_connection import get_connection
        from data_access.BalanceSheets import BalanceSheets as BS
        from data_access.IncomeStatements import IncomeStatements as IS
        from data_access.CashFlow import CashFlow as CF
        from data_access.OHLCVPriceData import OHLCVPriceData as OHLCV
        from data_access.EarningsReports import EarningsReports as ER
        from data_access.CompanyDetails import CompanyDetails as CD

        object.__setattr__(self,'ts',TS())
        object.__setattr__(self,'ticker',ticker)

        object.__setattr__(self,'conn',get_connection(readonly=True))

        object.__setattr__(self,'balance',balance)
        object.__setattr__(self,'cash',cash)
        object.__setattr__(self,'income',income)
        object.__setattr__(self,'earnings',earnings)
        object.__setattr__(self,'company_details',company_details)
        object.__setattr__(self,'ohlcv',ohlcv)
        object.__setattr__(self, 'last_error', None)

        if self.ticker is None or not isinstance(self.ticker, str) or self.ticker == '':
            raise ValueError("ticker must be a string")

        # check to see if the ticker is likely to have the data needed simply by checking it's market cap
        comp_details = pd.read_sql_query(
            "SELECT * FROM company_details",
            self.conn
        )
        ticker_list = comp_details.Symbol.tolist()
        if self.ticker not in ticker_list:
            raise ValueError(f"ticker '{self.ticker}' not found in company details database")

        if self.balance is None:
            self.balance = BS(self.ticker)
        if self.cash is None:
            self.cash = CF(self.ticker)
        if self.income is None:
            self.income = IS(self.ticker)
        if self.earnings is None:
            self.earnings = ER(self.ticker)

        if self.company_details is None:
            self.company_details = CD(self.ticker)
        if self.ohlcv is None:
            self.ohlcv = OHLCV(self.ticker)

        object.__setattr__(self,'datapresent', has_minimum_annual_history(self.ticker,10))
        object.__setattr__(self,'needed_columns', (
            'totalRevenue',
            'netIncome',
            'totalAssets',
            'totalLiabilities',
            'totalCurrentAssets',
            'totalNonCurrentAssets',
            'totalCurrentLiabilities',
            'totalNonCurrentLiabilities',
            'longTermDebt',
            'shortTermDebt',
            'shortLongTermDebtTotal',
            'commonStockSharesOutstanding',
            'cashAndCashEquivalentsAtCarryingValue',
            'inventory',
            'intangibleAssets',
            'intangibleAssetsExcludingGoodwill',
            'goodwill',
            'propertyPlantEquipment',
            'accumulatedDepreciationAmortizationPPE',
            'ebit',
            'ebitda',
            'reportedEPS',
            'paymentsForRepurchaseOfCommonStock',
            'paymentsForRepurchaseOfPreferredStock',
            'preferredStock',
            'dividendPayoutPreferredStock',
            'dividendPayoutCommonStock',
            'dividendPayout',
            'fiscalDateEnding',
            'closingSharePrice',
        ))


    def _empty_value_dataframe(self, reason: str) -> pd.DataFrame:
        """
        Return a schema-stable empty value dataframe and retain the failure reason.
        """
        self.last_error = reason
        print(reason)
        return pd.DataFrame(columns=[
            'fiscalDateEnding',
            'statement',
            'closingSharePrice',
            'epsTTM',
            'eps3YrAverage',
            'ebitTTM',
        ])


    @staticmethod
    def _annual_statement_frame(frame: pd.DataFrame) -> pd.DataFrame:
        """Normalize one annual statement for an exact fiscal-date join."""
        if frame is None or frame.empty or "fiscalDateEnding" not in frame:
            return pd.DataFrame()
        normalized = frame.copy()
        normalized["fiscalDateEnding"] = pd.to_datetime(
            normalized["fiscalDateEnding"],
            errors="coerce",
        )
        normalized = normalized.dropna(subset=["fiscalDateEnding"])
        normalized = normalized.drop_duplicates(
            "fiscalDateEnding",
            keep="first",
        )
        return normalized.set_index("fiscalDateEnding").sort_index()


    @staticmethod
    def _annual_common_dividend_status(
        fiscal_dates: pd.Series,
        dividend_history: pd.DataFrame,
    ) -> pd.Series:
        """Return paid/not-paid only for fully covered fiscal years."""
        status = pd.Series(
            pd.NA,
            index=fiscal_dates.index,
            dtype="boolean",
            name="commonStockDividendPaid",
        )
        required_columns = {"date", "dividend_amount"}
        if (
            dividend_history is None
            or dividend_history.empty
            or not required_columns.issubset(dividend_history.columns)
        ):
            return status

        history = dividend_history.loc[:, sorted(required_columns)].copy()
        history["date"] = pd.to_datetime(history["date"], errors="coerce")
        history["dividend_amount"] = pd.to_numeric(
            history["dividend_amount"],
            errors="coerce",
        )
        history = history.dropna(subset=["date"]).sort_values("date")
        if history.empty:
            return status

        max_boundary_gap = pd.Timedelta(days=7)
        max_internal_gap = pd.Timedelta(days=10)
        for idx, raw_fiscal_end in fiscal_dates.items():
            fiscal_end = pd.to_datetime(raw_fiscal_end, errors="coerce")
            if pd.isna(fiscal_end):
                continue
            fiscal_start = fiscal_end - pd.DateOffset(years=1)
            window = history[
                (history["date"] > fiscal_start)
                & (history["date"] <= fiscal_end)
            ]
            if window.empty or window["dividend_amount"].isna().any():
                continue
            if window["date"].min() - fiscal_start > max_boundary_gap:
                continue
            if fiscal_end - window["date"].max() > max_boundary_gap:
                continue
            if window["date"].diff().max() > max_internal_gap:
                continue
            status.loc[idx] = bool((window["dividend_amount"] > 0).any())

        return status


    def concat_dataframes(self) -> pd.DataFrame:
        """
        Create a dataframe consisting of the four main financial statements, and the
        share price history ('closing price').
        """
        needed_columns = self.needed_columns
        balance = self.balance.annual()
        cash = self.cash.annual()
        income = self.income.annual()
        earnings = self.earnings.annual()

        if balance.empty or cash.empty or income.empty or earnings.empty:
            print("all arguments must be non-empty pandas dataframes")
            return pd.DataFrame()

        statements = {
            "income": self._annual_statement_frame(income),
            "balance": self._annual_statement_frame(balance),
            "cash": self._annual_statement_frame(cash),
            "earnings": self._annual_statement_frame(earnings),
        }
        if any(frame.empty for frame in statements.values()):
            return pd.DataFrame()

        shared_dates = statements["balance"].index.intersection(
            statements["cash"].index
        ).intersection(statements["income"].index)
        if shared_dates.empty:
            return pd.DataFrame()

        merged = pd.DataFrame(index=shared_dates.sort_values())
        source_priority = ("income", "balance", "cash", "earnings")
        for column in needed_columns:
            if column == "fiscalDateEnding":
                continue
            combined = None
            for source in source_priority:
                frame = statements[source]
                if column not in frame.columns:
                    continue
                series = frame[column].reindex(merged.index)
                if combined is None:
                    combined = series
                else:
                    combined = combined.combine_first(series)
            if combined is not None:
                merged[column] = combined

        merged.index.name = "fiscalDateEnding"
        merged = merged.reset_index()
        available_columns = [
            column for column in needed_columns if column in merged.columns
        ]
        return transform_dataframe_dtypes(merged[available_columns])


    def create_value_dataframe(self, min_years: int = 10):
        """
        This function is to run the concatenated df through the various Graham value
        calculating functions to see if they stand up to Value Investing criteria.
        """
        if not isinstance(min_years, int) or min_years < 3:
            raise ValueError(f"min_years must be an integer greater than or equal to 3. Received {min_years}")

        n_columns = [*self.needed_columns]
        if 'closingSharePrice' in n_columns:
            n_columns.remove('closingSharePrice')

        _df = self.concat_dataframes()
        if _df.empty or _df.index.size < min_years:
            return self._empty_value_dataframe(
                f"{self.ticker} has insufficient annual data for analysis. "
                f"Required >= {min_years} years, found {len(_df.index)}."
            )

        # Preserve schema even when some GAAP fields are missing for a ticker.
        _df = _df.reindex(columns=n_columns).copy()

        # Normalize dates once so we can do calendar-year matching without relying on
        # string accessors, which break when the column is already datetime-typed.
        if 'fiscalDateEnding' not in _df.columns:
            return self._empty_value_dataframe(f"{self.ticker} data is missing fiscalDateEnding.")
        _df['fiscalDateEnding'] = pd.to_datetime(_df['fiscalDateEnding'])
        _df = _df.dropna(subset=['fiscalDateEnding'])
        _df = _df.sort_values('fiscalDateEnding').reset_index(drop=True)

        dividend_history = pd.DataFrame()
        dividend_history_loader = getattr(
            self.ohlcv,
            "dividend_history",
            None,
        )
        if callable(dividend_history_loader):
            dividend_history = dividend_history_loader()
        _df["commonStockDividendPaid"] = (
            self._annual_common_dividend_status(
                _df["fiscalDateEnding"],
                dividend_history,
            )
        )
        df_idx = [*_df.index]

        _3YR_EARNING_series = {}
        _3YR_EPS_series = {}

        for idx in df_idx:
            if idx >= len(df_idx) - 2:
                _3YR_EARNING_series[idx] = np.nan
                _3YR_EPS_series[idx] = np.nan
            else:
                _3YR_EPS_series[idx] = _df['reportedEPS'].iloc[idx:idx+3].mean()
                _3YR_EARNING_series[idx] = _df['netIncome'].iloc[idx:idx+3].mean()

        _df['earnings3YrAverage'] = pd.Series(_3YR_EARNING_series.values(),index=_3YR_EARNING_series.keys())
        _df['eps3YrAverage'] = pd.Series(_3YR_EPS_series.values(),index=_3YR_EPS_series.keys())

        price_history = self.ohlcv.closing_prices()
        if price_history is None or price_history.empty:
            return self._empty_value_dataframe(f"{self.ticker} has no OHLCV price history available.")

        earliest_price_date = pd.DatetimeIndex(price_history.index).min()

        for date in _df['fiscalDateEnding'].dropna().unique():
            min_dt = pd.Timestamp(date) + pd.Timedelta(days=37)
            max_dt = pd.Timestamp(date) + pd.Timedelta(days=45)

            if min_dt < earliest_price_date:
                continue

            mindate = min_dt.strftime("%Y-%m-%d")
            maxdate = max_dt.strftime("%Y-%m-%d")

            try:
                price_window = self.ohlcv.price_range(mindate, maxdate)
            except ValueError:
                continue

            if price_window is None or price_window.empty:
                continue

            price_range = price_window.close.min()
            if pd.isna(price_range):
                continue

            _df.loc[_df['fiscalDateEnding'].eq(date), 'closingSharePrice'] = price_range

        _df.sort_values(by='fiscalDateEnding', ascending=False, inplace=True)
        _df.reset_index(drop=True, inplace=True)
        _df.dropna(axis=0,subset=['fiscalDateEnding'], inplace=True)

        return _df


    def quarterly_data(self):
        """
        Create a dataframe that has the quarterly EBIT data and the accompanying share price that lays 7-14
        days AFTER the date the report was published (per J. Greenblatt's magic formula details).
        :return:
        """
        ticker = self.ticker
        inc = self.income.quarterly()
        eps = self.earnings.quarterly()
        if inc is None or inc.empty:
            print(f"{ticker} has no quarterly income statement data.")
            return None
        if eps is None or eps.empty:
            print(f"{ticker} has no quarterly earnings data.")
            return None

        inc = inc[['fiscalDateEnding', 'ebit', 'netIncome']]
        eps = eps[['fiscalDateEnding', 'reportedEPS', 'epsTTM']]
        df = pd.merge(inc, eps, on='fiscalDateEnding', how='left')

        df['fiscalDateEnding'] = pd.to_datetime(df['fiscalDateEnding'])
        df = df.dropna(subset=['fiscalDateEnding'])
        df = df.sort_values('fiscalDateEnding', ascending=False).reset_index(drop=True)

        # Build each TTM value from the current quarter and the next three
        # older quarters. Incomplete four-quarter windows remain unavailable.
        IDX_LEN = len(df.index)

        if IDX_LEN < 20:
            print(f"{ticker} needs at least 5 years quarterly data to be considered for analysis.")
            return None
        df['ebitTTM'] = np.nan
        df['earningsTTM'] = np.nan
        for i in range(max(0, IDX_LEN - 3)):
            df.loc[i, 'ebitTTM'] = pd.to_numeric(
                df['ebit'].iloc[i:i + 4], errors='coerce'
            ).sum(min_count=4)
            df.loc[i, 'earningsTTM'] = pd.to_numeric(
                df['netIncome'].iloc[i:i + 4], errors='coerce'
            ).sum(min_count=4)

        # share price history
        ohlcv = self.ohlcv

        # SEC rules state the filer has up to 45 days to submit quarterly, and 90 to submit annual reports
        # for that reason, selecting on the first date of the quarter will be used, understanding that the report
        # retrieved on that date, is actually the previous the quarters report...
        # If the quarter date is not fiscal year-end date: then delta is +45 days, else: +
        # set the dates to reflect taking the share price min. 7 days after the date of the report

        for date in df['fiscalDateEnding'].dropna().unique():
            mindate = date + pd.Timedelta(days=37)
            maxdate = date + pd.Timedelta(days=45)
            mindate = mindate.strftime("%Y-%m-%d")
            maxdate = maxdate.strftime("%Y-%m-%d")
            price_window = ohlcv.price_range(mindate, maxdate)
            if price_window is None or price_window.empty:
                continue

            price_range = price_window.close.min()
            if pd.isna(price_range):
                continue

            df.loc[df['fiscalDateEnding'].eq(date), 'closingSharePrice'] = price_range

        df.sort_values(by='fiscalDateEnding', ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.drop('ebit',inplace=True,axis=1)

        # detail which fiscal statement is used for value used
        co = self.company_details.get_details()
        fiscal_end_month = co.get('FiscalYearEnd')
        if fiscal_end_month is None:
            return self._empty_value_dataframe(f"No fiscal year end month found for ticker: {self.ticker}")

        if fiscal_end_month is None:
            return self._empty_value_dataframe(f"Invalid fiscal year end month found for ticker: {self.ticker}")

        for i, d in df['fiscalDateEnding'].to_dict().items():
            if d.strftime('%B') == fiscal_end_month:
                df.loc[i, 'statement'] = 'Annual'
            elif d.strftime('%B') is None or d.strftime('%B') == '':
                df.loc[i, 'statement'] = ''
            else:
                df.loc[i, 'statement'] = 'Quarterly'
        return df


    def company_market_fye_quarter_sector_industry_info(self):
        """
        Retrieve company details, sector, and industry information for all SEC tickers.
        """
        from data_access.CompanyDetails import CompanyDetails
        from data_ingestion.TickerFileSearch import TickerSearch

        all_tickers = pd.read_sql_query(
            "SELECT ticker FROM sec_tickers",
            self.conn
        )
        all_tickers = all_tickers.ticker.tolist()
        company_details = {}
        sectors = []
        industries = []

        for ticker in all_tickers:
            co_deets = CompanyDetails().get_details(ticker)
            alternative = TickerSearch().ticker_search_information(ticker)
            if co_deets is None:
                continue
            market_cap = pd.read_sql_query(
                f"SELECT * FROM market_capitalization WHERE ticker = '{ticker}'",
                self.conn
            )
            if market_cap.empty:
                marketCap = 0
                marketCapGroup = None
            else:
                marketCap = market_cap.marketCapitalization.iloc[0]
                marketCapGroup = market_cap.marketCapGroup.iloc[0]
            fiscal_year = co_deets.get("FiscalYearEnd")
            latest_q = co_deets.get("LatestQuarter")
            sector = co_deets.get("Sector")
            industry = co_deets.get("Industry")
            assettype = co_deets.get("AssetType")
            name = co_deets.get('Name')

            if name is None and alternative:
                alt_name = alternative.get('2. name')
                if alt_name is None or alt_name == {}:
                    pass
                else:
                    name = alt_name
            if assettype is None and alternative:
                alt_asset_type = alternative.get('3. type')
                if alt_asset_type is None or alt_asset_type == {}:
                    pass
                else:
                    assettype = alt_asset_type

            company_details[ticker] = {
                'ticker': ticker,
                'name': name,
                'asset_type': assettype,
                'market_cap': marketCap,
                'market_cap_group':marketCapGroup,
                'fiscal_date': fiscal_year,
                'latest_q': latest_q,
                'sector': sector,
                'industry': industry,
            }
            sectors.append(sector)
            industries.append(industry)

        df = pd.DataFrame(company_details.values(), index=company_details.keys())
        df.index.name = 'ticker'

        return df

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class FinancialData_by_date:
    """Return a safe, date-selected financial snapshot for one security."""

    def __init__(self, ticker, analysis_date: None | str = None):
        if not ticker or not isinstance(ticker, str):
            raise ValueError("Ticker must be a non-empty string")
        ticker = ticker.upper()
        if analysis_date is not None:
            if not isinstance(analysis_date, str):
                raise TypeError(
                    "Analysis date must be a string in the format 'YYYY-MM-DD'"
                )
            try:
                analysis_date = dt.date.fromisoformat(analysis_date).isoformat()
            except ValueError as exc:
                raise ValueError(
                    "Analysis date must be in the format 'YYYY-MM-DD'"
                ) from exc
        else:
            analysis_date = dt.date.today().isoformat()

        from data_access.BalanceSheets import BalanceSheets as BS
        from data_access.IncomeStatements import IncomeStatements as IS
        from data_access.CashFlow import CashFlow as CF
        from data_access.OHLCVPriceData import OHLCVPriceData as OHLCV
        from data_access.EarningsReports import EarningsReports as ER

        balance = BS(ticker=ticker)
        cash_flow = CF(ticker=ticker)
        income = IS(ticker=ticker)
        earnings = ER(ticker=ticker)
        price_history = OHLCV(ticker=ticker)

        bal = self._safe_date_lookup(balance, analysis_date)
        cash = self._safe_date_lookup(cash_flow, analysis_date)
        inc = self._safe_date_lookup(income, analysis_date)
        earn = self._safe_date_lookup(earnings, analysis_date)
        price_record = self._safe_price_lookup(price_history, analysis_date)

        object.__setattr__(self, 'ticker', ticker)
        object.__setattr__(self, 'analysis_date', analysis_date)
        object.__setattr__(self, 'balance', bal)
        object.__setattr__(self, 'cash', cash)
        object.__setattr__(self, 'income', inc)
        object.__setattr__(self, 'earnings', earn)
        object.__setattr__(self, 'price', price_record.get('close', np.nan))
        object.__setattr__(
            self,
            'ttm',
            self._trailing_twelve_months(
                income.quarterly(),
                earnings.quarterly(),
                analysis_date,
            ),
        )

    @staticmethod
    def _safe_date_lookup(accessor, analysis_date: str) -> dict:
        try:
            return accessor.get_by_date(analysis_date) or {}
        except (KeyError, TypeError, ValueError):
            return {}

    @staticmethod
    def _safe_price_lookup(price_history, analysis_date: str) -> dict:
        try:
            return price_history.price_on_date(analysis_date) or {}
        except (KeyError, TypeError, ValueError):
            return {}

    @staticmethod
    def _latest_four_quarters(
            df: pd.DataFrame,
            analysis_date: str,
    ) -> pd.DataFrame:
        if df is None or df.empty or 'fiscalDateEnding' not in df.columns:
            return pd.DataFrame()
        result = df.copy()
        result['fiscalDateEnding'] = pd.to_datetime(
            result['fiscalDateEnding'], errors='coerce'
        )
        result = result.dropna(subset=['fiscalDateEnding'])
        result = result[
            result['fiscalDateEnding'] <= pd.Timestamp(analysis_date)
        ]
        return (
            result.sort_values('fiscalDateEnding', ascending=False)
            .drop_duplicates('fiscalDateEnding')
            .head(4)
        )

    @classmethod
    def _trailing_twelve_months(
            cls,
            income: pd.DataFrame,
            earnings: pd.DataFrame,
            analysis_date: str,
    ) -> dict:
        income = cls._latest_four_quarters(income, analysis_date)
        earnings = cls._latest_four_quarters(earnings, analysis_date)

        def four_quarter_sum(frame: pd.DataFrame, column: str):
            if len(frame.index) != 4 or column not in frame.columns:
                return np.nan
            values = pd.to_numeric(frame[column], errors='coerce')
            return values.sum(min_count=4)

        return {
            'epsTTM': four_quarter_sum(earnings, 'reportedEPS'),
            'earningsTTM': four_quarter_sum(income, 'netIncome'),
            'ebitTTM': four_quarter_sum(income, 'ebit'),
        }

    def to_dict(self) -> dict:
        financials = {}
        for statement in (self.balance, self.cash, self.income, self.earnings):
            financials.update(statement or {})
        financials.update(self.ttm)
        financials.update({
            'ticker': self.ticker,
            'analysis_date': self.analysis_date,
            'price': self.price,
        })
        fiscal_date = financials.get('fiscalDateEnding')
        if hasattr(fiscal_date, 'isoformat'):
            financials['fiscalDateEnding'] = fiscal_date.isoformat()
        return financials

    def get_closest_date(self) -> dict:
        """Backward-compatible alias for the date-selected financial snapshot."""
        return self.to_dict()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def _has_annual_statement_history(
    df: pd.DataFrame,
    years: int,
    date_col: str = "fiscalDateEnding",
) -> bool:
    if df is None or df.empty or date_col not in df.columns:
        return False
    if years < 1:
        return False

    fiscal_dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    fiscal_dates = fiscal_dates.drop_duplicates()
    if len(fiscal_dates) < years:
        return False

    date_span = fiscal_dates.max() - fiscal_dates.min()
    required_span = pd.Timedelta(days=365 * (years - 1))
    return date_span >= required_span


def has_annual_earnings_history(ticker: str, years: int) -> bool:
    from data_access.EarningsReports import EarningsReports as ER

    return _has_annual_statement_history(ER(ticker).annual(), years)


def has_annual_balance_history(ticker: str, years: int) -> bool:
    from data_access.BalanceSheets import BalanceSheets as BS

    return _has_annual_statement_history(BS(ticker).annual(), years)


def has_annual_income_history(ticker: str, years: int) -> bool:
    from data_access.IncomeStatements import IncomeStatements as IS

    return _has_annual_statement_history(IS(ticker).annual(), years)


def has_annual_cash_flow_history(ticker: str, years: int) -> bool:
    from data_access.CashFlow import CashFlow as CS

    return _has_annual_statement_history(CS(ticker).annual(), years)


def has_price_history(ticker: str, years: int) -> bool:
    from data_access.OHLCVPriceData import OHLCVPriceData as OHLCV

    _ph = OHLCV(ticker).closing_prices()
    if _ph is None or _ph.empty or years < 1:
        return False

    price_dates = pd.to_datetime(_ph.index, errors="coerce")
    price_dates = pd.Series(price_dates).dropna()
    if price_dates.empty:
        return False

    date_span = price_dates.max() - price_dates.min()
    required_span = pd.Timedelta(days=365 * (years - 1))
    return date_span >= required_span


def has_enterprising_history(ticker: str) -> bool:
    return all((
        has_annual_income_history(ticker, years=5),
        has_annual_cash_flow_history(ticker, years=5),
        has_annual_balance_history(ticker, years=5),
        has_annual_earnings_history(ticker, years=5),
        has_price_history(ticker, years=5),
    ))


def has_defensive_history(ticker: str) -> bool:
    return all((
        has_annual_income_history(ticker, years=10),
        has_annual_cash_flow_history(ticker, years=10),
        has_annual_balance_history(ticker, years=10),
        has_annual_earnings_history(ticker, years=10),
        has_price_history(ticker, years=10),
    ))


def has_minimum_annual_history(ticker: str,years: int):
    if years < 5:
        print(f"Arg 'years' must be greater than or equal to 5. Years entered = {years}")
        return False
    return all((
        has_annual_income_history(ticker, years=years),
        has_annual_cash_flow_history(ticker, years=years),
        has_annual_balance_history(ticker, years=years),
        has_annual_earnings_history(ticker, years=years),
        has_price_history(ticker, years=years),
    ))
