"""
Create a class of objects to get various values which would signal action on a security based off of it's share price
during given periods, or in various conditions
"""

import pandas as pd
import datetime as dt
import numpy as np
from data_access.OHLCVPriceData import OHLCVPriceData as OHLCV
from Securities_DB.db_connection import get_connection


holidays = (
    '2025-01-01',
    '2025-01-20',
    '2025-02-17',
    '2025-04-11',
    '2025-05-26',
    '2025-06-19',
    '2025-07-04',
    '2025-09-01',
    '2025-10-13',
    '2025-11-27',
    '2025-12-24',
    '2025-12-25',
)
holidays = [np.datetime64(holiday) for holiday in holidays]


class MovingAverageSignals:
    """
    Create a class of objects to get various values which would signal action on a security based off of it's share price
    during given periods, or in various conditions
    """
    # initialize the class object with the asset's closing prices
    def __init__(self, ticker:str,start:str|None=None,end:str|None=None,period:int|None=None):

        """
        'start' date is the period in history which all calculations will begin from. If end date is provided,
        then it must be later than the start date. I shall be entered as a string in the format 'YYYY-MM-DD'.
        If period is not provided, the default period will be a 5 day period
        The class will return data points related to the various MA indicator signals through
         their associated methods.
        """
        if ticker is None:
            raise ValueError(f"Ticker must be provided")
        elif not isinstance(ticker,str):
            raise ValueError(f"Ticker must be a string")
        ticker = ticker.upper() if not ticker.isupper() else ticker

        object.__setattr__(self, 'ticker',ticker)

        if start is None:
            start = dt.datetime.today()
            if period is None or period < 5:
                start = dt.datetime.today() - dt.timedelta(days=5)
            start = start.strftime("%Y-%m-%d")
        elif isinstance(start,str):
            if len(start) != 10:
                raise ValueError(f"Start date must be in the format 'YYYY-MM-DD'")
            elif len(start.split('-')) != 3:
                raise ValueError(f"Start date must be in the format 'YYYY-MM-DD'")
            elif not all(x.isnumeric() for x in start.split('-')):
                raise ValueError(f"Start date must be in the format 'YYYY-MM-DD'")
        else:
            raise ValueError(f"Start date must be string, in the format 'YYYY-MM-DD'")

        if period is None:
            period = 5
            object.__setattr__(self, 'period',period)
        else:
            if period <= 0:
                raise ValueError(f"Period must be positive integer")
            object.__setattr__(self, 'period',period)
        object.__setattr__(self, 'start',start)

        if end is None:
            end = dt.datetime.fromisoformat(start) + dt.timedelta(days=self.period)
            end = end.strftime("%Y-%m-%d")
        object.__setattr__(self, 'end',end)

        ohlcv = OHLCV(self.ticker)
        df = ohlcv.daily_prices()
        price_range = ohlcv.price_range(start,end).iloc[-1::-1]
        price_range.reset_index(drop=True,inplace=True)
        df_close = ohlcv.closing_prices().iloc[-1::-1]
        if any((df.empty, df_close.empty,price_range.empty)):
            raise ValueError(f"No data found for the given ticker and date range")

        object.__setattr__(self, 'df',df)
        object.__setattr__(self, 'price_range',price_range)
        object.__setattr__(self, 'df_close',df_close)

        # for some functions, you will need at least 2 * period + 1 data points to calculate the indicator
        L = len(df.index)
        pp = self.period * 2
        minimum = (L - pp + 1)

        if minimum < 0:
            raise ValueError(f"Period is greater than the number of data points in the dataframe.")

    # create a function to get the buy signal
    def buy_signal(self):
        return NotImplemented

    def sell_signal(self):
        return NotImplemented

    # create a function to get the sell signal

    def sma(self):
        """
        simple moving average for period given. If kwarg 'period' is None, then period is set to 20 days.
        Keep in mind, the days will be single rows for daily could be multiple datapoints across a timeframe
        for intraday data.
        """
        # determine the size of the dataframe, and capture just the 'close' column.

        return self.price_range['close'].mean()

    def ema_dema_tema(self, period: int|None = None) -> tuple:
        """
        returns EMA, DEMA, and TEMA values for the given period as a tuple, respectively.
        Period does not need to be provided unless you're using EMA for another indicator and you need a
        different value for the period than the original class arg (self.period).

        Signal based on exponential moving average, i.e. dynamic mean
        measures the rate of change from one SMA to the next. Used as a basis for other signal's formulas.
        Period does not need to be provided unless you're using EMA for another indicator and you need a
        different value for the period than the original class arg (self.period).

        Common EMA periods are [12,26,9] (for MACD), and 50,100,200 for long term trend,
        and 5,9,10,14, and 20 for short term trend.

        s_0 = x_0 -> mean for period x in the first period (no alpha factor applied)
        """
        if period is None:
            period = self.period
        elif period <= 5:
            raise ValueError(f"Period must be greater than 5")

        _df = self.df_close.copy()

        alpha = (2 / (period + 1))
        x_0 = _df.iloc[0]
        sma_prev = _df.iloc[1:period + 1].mean()

        ema = (x_0 * alpha) + (sma_prev * (1 - alpha))

        x_n_1 = _df.iloc[period]
        sma_prev_1 = _df.iloc[period + 1:2 * period + 1].mean()

        ema_1 = (x_n_1 * alpha) + (sma_prev_1 * (1 - alpha))

        dema = (2 * ema) - ema_1

        x_n_2 = _df.iloc[2 * period]
        sma_prev_2 = _df.iloc[2 * period + 1:3 * period + 1].mean()

        ema_2 = (x_n_2 * alpha) + (sma_prev_2 * (1 - alpha))

        tema = (3 * ema) - (3 * dema) + ema_2

        return ema.iloc[0], dema.iloc[0], tema.iloc[0]


    def macd(self) -> tuple:
        """
        MACD line crossing above 0 = buy signal
        26 previous EMA's - 12 previous EMA's = MACD line
        9 previous EMA's - MACD line = signal line
        signal line crossing above MACD line = buy signal
        signal line crossing below MACD line = sell signal
        histogram crossing above 0 = buy signal
        histogram crossing below 0 = sell signal
        Returns a tuple of length 3 containing MACD line, signal line, and histogram, respectively.

        """
        ema_12 = self.ema_dema_tema(period=12)[0]
        ema_26 = self.ema_dema_tema(period=26)[0]
        ema_9 = self.ema_dema_tema(period=9)[0]

        MACDline = ema_12 - ema_26
        signal_line = ema_9 - MACDline
        histogram = signal_line - MACDline

        return MACDline, signal_line, histogram

    def ibs(self):
        """
        signal based on mean reversion that the average will revert to the mean
        (CP-LO)/(HI-LO) -> ranges 0-1, with 0 being the lowest and 1 being the highest and
        where that number lands helps indicate price reversal/trend reversals buy signal at low (<.2),
        and sell signal at high (>0.9). Good in volatile/bear markets. Not good with Commodity stocks though.
        Closer to 0 means the SP is closer to the LOW, and closer to 1 means the SP is closer to the HIGH.
        """
        # determine the size of the dataframe, and capture just the 'close' column.
        df = self.price_range.copy()
        cp = df.close
        lo = df.low
        hi = df.high

        ibs = (cp - lo) / (hi - lo)
        return ibs

    def psar(self) -> pd.DataFrame:
        """
        Returns a dataframe object with psar values and trend values for the given period.
        parabolic stop and reverse that indicates when to enter or leave a trade based on momentum and trend
        SAR_n+1 = SAR_n + af * (EP - SAR_n) where 'EP' is the extreme price (High or Low) for the period
        (generally a day). The EP is either the high or the low based on the 'trend'. If previous day
        was up, then the EP is the high. If previous day was down, then the EP is the low. If it's the
        opposite of the previous day, it marks a reversal.

        """
        df = self.df.copy()

        _df = df.iloc[-1::-1].copy()  # reverse the dataframe to start from the end of the period
        SAR_n = _df.iloc[1].close
        SAR_n1 = _df.iloc[0].close
        af = .02
        afmax = .02
        up, down, reverse = True, False, None
        Low, High = _df.iloc[1].low, _df.iloc[1].high
        psarlist = []

        if SAR_n > SAR_n1:
            trend = up
            psar = SAR_n + af * (High - SAR_n)
            psarlist.append((_df.index[1].date(), psar, trend))
        elif SAR_n < SAR_n1:
            trend = down
            psar = SAR_n + af * (Low - SAR_n)
            psarlist.append((_df.index[1].date(), psar, trend))
        else:
            trend = reverse
            psar = None

        for i in range(2, len(_df.index) - 1):
            High, Low = _df.iloc[i].high, _df.iloc[i].low
            SAR_n, SAR_n1 = _df.iloc[i].close, _df.iloc[i - 1].close
            if SAR_n > SAR_n1 and trend is up:
                af = .002
                afmax += af
                if afmax > .2:
                    pass
                psar = SAR_n + af * (High - SAR_n)
            elif SAR_n < SAR_n1 and trend is down:
                af = .02
                psar = reverse
                trend = reverse
                afmax = .02
            elif SAR_n > SAR_n1 and trend is reverse:
                psar = SAR_n + af * (High - SAR_n)
                trend = up
            elif SAR_n < SAR_n1 and trend is up:
                af = .02
                psar = reverse
                trend = reverse
                afmax = .02
            elif SAR_n < SAR_n1 and trend is down:
                af = .002
                afmax += af
                if afmax > .2:
                    pass
                psar = SAR_n + af * (Low - SAR_n)
                trend = down
            else:
                psar = reverse
                trend = reverse
                af = .02

            psarlist.append((_df.index[i].date(), psar, trend))
        # Dataframe created from the psarlist with 'psar' in one column, and 'trend' in another
        # True is up, False is down, and None is a reversal in trend from the previous day
        # str - Trend is the equivalent of True, False, and None
        psl = [psarlist[j][1] for j in range(len(psarlist))]
        tsl = [psarlist[j][2] for j in range(len(psarlist))]
        str_tsl = ['up' if psarlist[j][2] is True else 'down' if psarlist[j][2] is False else 'reverse' for j in
                   range(len(psarlist))]
        dl = [psarlist[j][0] for j in range(len(psarlist))]
        dfpsar = pd.DataFrame(
            {'psar': psl, 'trend': tsl, 'str_trend': str_tsl},
            columns=['psar', 'trend', 'str_trend'],
            index=dl
        )
        dfpsar = dfpsar.iloc[-1::-1]

        return dfpsar

    def avg_true_return(self) -> pd.Series:
        """
        average true return is a measure of the average return of a stock over a period of time.
        The period is given in number of days (period) and defaults to 5.
        for a single period::=ATR = sum(TR) * (1/_p) where TR = max(hilo,hi_prev_close,lo_prev_close)
        ATR's of subsequent periods can be calculated by ATR = (ATR * (n-1) + TR) / n
        Those are used to compare against current ATR to determine volatility and stop-loss level (SP-(ATR * 1.5))
        """
        df = self.price_range.iloc[::-1].copy()  # Use chronological order for calculation
        _p = self.period

        hilo = df['high'] - df['low']
        hilo.name = 'high-low'

        hi_prev_close = (df['high'] - df['close'].shift(1)).abs()
        hi_prev_close.name = 'high-prev-close'
        lo_prev_close = (df['low'] - df['close'].shift(1)).abs()
        lo_prev_close.name = 'low-prev-close'

        # Reduce only the true-range components. Avoid ever including date or other metadata columns here,
        # because pandas will try to compare timestamps against floats during the row-wise max.
        tr_components = pd.concat([hilo, hi_prev_close, lo_prev_close], axis=1)
        tr = tr_components.max(axis=1, numeric_only=True)
        atr = tr.rolling(window=_p).mean()

        # Reverse back to latest-first to match self.price_range orientation
        atr = atr.iloc[::-1]
        atr.name = 'averageTrueReturn'
        
        return atr