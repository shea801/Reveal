# python 3.14
import pandas as pd
import numpy as np

from analytics.GrahamInvestorClasses import EnterprisingInvestor as EI, DefensiveInvestor as DI
from Securities_DB.db_connection import get_connection
from data_access.PipelineETL import FinancialData as FD

"""
This python file is to used to help script the functions which will analyze financial 
data from the various financial sheets and price history. The applications will 
determine whether a common stock is worth investing in. It will determine the stocks
Graham Number/Serenity Number, it's intrinsic value, and its 'MARGIN OF SAFETY'
"""


# first will be a class type for the 'Defensive Investor'
class ValueInvestor:
    """
    Use this class to iterate through a list of Common Stock symbols which represent a vetted list of Securities which
    has been through a previous ETL process. The 'tkr_sym_lst' kwarg is optional. If 'None', the class will pull the
    proper file to load a vetted list of common stock securities.

    The class will have three methods: defensive_investor, enterprising_investor, and net_net. The first two,
    respectively, are dataframes with the appropriate category for the defensive or enterprising investor criteria.
    Net-net is a dataframe with the appropriate category for the net-net value of common stocks, but it works using
    twelve-month trailing data (TTM). IT'S THE ONLY TIME GRAHAM ALLOWED UNACCOUNTED FINANCIAL INFO (i.e. quarterly data
     whose accounting is not subject to US-GAAP standards).
    """

    def __init__(self, tickerlist: list = None):
        # Coerce pandas Index / Series / ndarray / tuple into a plain list,
        # and use `is not None` to avoid pandas' ambiguous-truth-value error.
        conn = get_connection(readonly=True)
        tickers_df = pd.read_sql_query(
            "SELECT ticker FROM market_capitalization",
            conn
        )
        _ticker_check = tickers_df['ticker'].tolist()
        if isinstance(tickerlist, list) and tickerlist != []:
            _ticker_check = [i for i in tickerlist if i in _ticker_check]
        else:
            _ticker_check = tickers_df['ticker'].tolist()

        object.__setattr__(self, 'tickerlist',_ticker_check)
        object.__setattr__(self, '_ticker_check',_ticker_check)


    def defensive_investor(self) -> pd.DataFrame:
        """
        This function is to run the concatenated df through the various Graham value
        calculating functions to see if they stand up to Value Investing criteria.
        """
        tlist = self.tickerlist.copy()
        defensive_inv = {}
        while tlist:
            ticker = tlist.pop(-1)
            try:
                di = DI(ticker)
                criteria = {
                    'fiscalDateEnding': di.fiscalDateEnding,
                    'grahamNumber': di.graham_number,
                    'defensiveMarginOfSafety': di.defensive_margin_of_safety(),
                }
                ticker_df = pd.DataFrame(criteria, index=[0])
                defensive_inv[ticker] = ticker_df
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                continue

        if defensive_inv:
            combined = pd.concat(defensive_inv, names=['ticker', 'idx'])
            return combined
        else:
            return pd.DataFrame()

    def enterprising_investor(self) -> pd.DataFrame:
        """Determine if a common stock meets Ben Graham's enterprise investor criteria:
        current assets >= 1.5x current liabilities,
        1.1 * long-term debt <= net current assets,
        positive earning for the past 5 years,
        some current dividend payments,
        earnings growth > earnings 4 yrs ago,
        current price <= 120% net tangible assets,
        """
        tlist = self.tickerlist.copy()
        enterprising_inv = {}
        while tlist:
            ticker = tlist.pop(-1)
            try:
                ei = EI(ticker)

                criteria = {
                    'fiscalDateEnding': ei.fiscalDateEnding,
                    'serenityNumber': ei.serenity_number(),
                    'enterprisingMarginOfSafety': ei.enterprising_margin_of_safety(),
                }
                ticker_df = pd.DataFrame(criteria, index=[0])
                enterprising_inv[ticker] = ticker_df
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                continue

        if enterprising_inv:
            combined = pd.concat(enterprising_inv, names=['ticker', 'idx'])
            return combined
        else:
            return pd.DataFrame()


    def net_net(self):
        """
        ( (Current Assets - Total Liabilities - Preferred Stock) / Common Shares Outstanding ) ** .5
        No net losses in the past 12 months (this is the only time you'll use Monthly and Quarterly data
         in a Graham evaluation).
        """
        netnet_results = {}
        tlist = self.tickerlist.copy()

        while tlist:
            ticker = tlist.pop(-1)
            try:
                df = FD(ticker).create_value_dataframe()
                if df is None or df.empty:
                    print(f"{ticker} is empty or has no data")
                    continue
                elif len(df.index) < 3:
                    print(f"{ticker} has less than 3 data points. Excluding {ticker}")
                    continue
                else:
                    criteria = {
                        'fiscalDateEnding': df.loc[:,'fiscalDateEnding'],
                        'currentAssets': df.loc[:,'totalCurrentAssets'],
                        'totalLiabilities': df.loc[:,'totalLiabilities'],
                        'preferredStock': df.loc[:,'preferredStock'] if 'preferredStock' in df.columns else 0,
                        'commonSharesOutstanding': df.loc[:,'commonStockSharesOutstanding'].replace([0,np.inf,-np.inf],np.nan),
                        'closingSharePrice': df.loc[:,'closingSharePrice']
                    }
                    calculated_net_net = (
                            (
                                    (criteria.get('currentAssets',0) - criteria.get('totalLiabilities',0) - criteria.get('preferredStock',0)) /
                                criteria.get('commonSharesOutstanding',np.nan)
                            ) ** .5)
                    netnet_results[ticker] = pd.DataFrame(
                        {
                            'net_current_asset_value': calculated_net_net,
                            'net_net': calculated_net_net / criteria.get('closingSharePrice',np.nan),
                            'fiscalDateEnding': criteria.get('fiscalDateEnding',None)
                        }, index=[0])
            except Exception as e:
                print(f"Error processing {ticker} in net_net: {e}")
                continue
        return netnet_results

