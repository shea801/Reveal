"""
Create class objects to get the various signals for volume of a security over various periods
"""
from turtledemo.penrose import start

import pandas as pd
import datetime as dt
import numpy as np

class AvgPeriodicVolume:
    def __init__(self,ticker:str,days:int=12):
        """
        'day','month', and 'year' can be entered as integers: day of the month, month of the year, and year respectively.
        The class will return data points related to the various Volume indicator signals through their associated
        methods.
        """
        from data_access.OHLCVPriceData import OHLCVPriceData as OHLCV

        if not isinstance(ticker, str):
            raise TypeError(f"Ticker must be a string.")
        ticker = ticker.upper() if not ticker.isupper() else ticker

        object.__setattr__(self, '_ticker', ticker)

        ohlcv = OHLCV(ticker)
        df = ohlcv.daily_prices()
        df_close = ohlcv.closing_prices()

        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError(f"OHLCV dataframe for ticker {ticker} is not a valid DataFrame.")
        if not isinstance(df_close, pd.DataFrame) or df_close.empty:
            raise ValueError(f"OHLCV dataframe for ticker {ticker} is not a valid DataFrame.")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days must be a positive integer.")
        N = days + 1
        if N >= df.index.size:
            if N == df.index.size:
                N -= 1
            else:
                raise ValueError(f"days must be less than or equal to the number of available days.")

        # obtain date range
        end_date = pd.to_datetime(df.date.iloc[0])
        end = end_date.strftime("%Y-%m-%d")
        start_date = end_date - dt.timedelta(days=N)
        start = start_date.strftime("%Y-%m-%d")
        # create the price range dataframe
        try:
            if not isinstance(start, str) or not isinstance(end, str):
                raise ValueError(f"start and end must be strings.")
            price_range = ohlcv.price_range(start, end)
        except ValueError as e:
            raise ValueError(f"Failed to create price range dataframe: {e}")

        price_range = price_range.iloc[-1::-1]
        price_range.reset_index(drop=True,inplace=True)

        object.__setattr__(self, 'df', df)
        object.__setattr__(self, 'df_close', df_close)
        object.__setattr__(self, 'price_range', price_range)
        object.__setattr__(self, 'ohlcv', ohlcv)
        object.__setattr__(self, 'days', days)
        object.__setattr__(self, 'N', N)
        object.__setattr__(self, 'start_date', start_date)
        object.__setattr__(self, 'end_date', end_date)
        object.__setattr__(self, 'start', start)
        object.__setattr__(self, 'end', end)


    def VWAP(self):
        """
        Calculates the volume weighted average price by considering the volume of the
        trade at various prices during a trading day. Not generally used other than intraday trading
        for the purpose of buying or selling at the optimum time. Need the full dataframe to calculate
        the VWAP, not just the volume. Good for mean reversion and trend following strategies.
        Calculates as follows: TP = [H + L + C] / 3], TP * V per period (may be hourly or minute wise).
        Those values are then summed together and divided by the total volume (cummalitive volume) for the period.
        """
        price_range = self.price_range

        # obtain price objects
        hi = price_range.high
        lo = price_range.low
        close = price_range.close

        SUM_TP = hi + lo + close
        TP = SUM_TP / 3

        vol = price_range.volume
        vwap = (vol * TP).sum() / vol.sum()

        return vwap

    def obv(self):
        """
        On Balance Volume is a technical indicator that measures the cumulative volume of a security's
        price movement. It is calculated by comparing the current day's closing price to the previous day's
        closing price. If the current day's closing price is higher than the previous day's closing price,
        the OBV is positive. If the current day's closing price is lower than the previous day's closing price,
        the OBV is negative.
        """
        price_range = self.price_range

        obv = 0
        for i in range(len(price_range.index) - 1):
            if price_range.close.iloc[i] > price_range.close.iloc[i + 1]:
                obv += 1
            elif price_range.close.iloc[i] < price_range.close.iloc[i + 1]:
                obv -= 1
            else:
                obv += 0
        return obv


class OscillatingSignals:
    def __init__(self, ticker:str,days:int=12):
        """
        'day','month', and 'year' can be entered as integers: day of the month, month of the year, and year respectively.
        The class will return data points related to the various MA indicator signals through their associated
        methods.
        """
        from data_access.OHLCVPriceData import OHLCVPriceData as OHLCV

        if not isinstance(ticker, str):
            raise TypeError(f"Ticker must be a string.")
        ticker = ticker.upper() if not ticker.isupper() else ticker

        object.__setattr__(self, '_ticker', ticker)

        ohlcv = OHLCV(ticker)
        df = ohlcv.daily_prices()
        df_close = ohlcv.closing_prices()

        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError(f"OHLCV dataframe for ticker {ticker} is not a valid DataFrame.")
        if not isinstance(df_close, pd.DataFrame) or df_close.empty:
            raise ValueError(f"OHLCV dataframe for ticker {ticker} is not a valid DataFrame.")
        if not isinstance(days, int) or days <= 0:
            raise ValueError(f"days must be a positive integer.")
        N = days + 1
        if N >= df.index.size:
            if N == df.index.size:
                N -= 1
            else:
                raise ValueError(f"days must be less than or equal to the number of available days.")

        # obtain date range
        end_date = pd.to_datetime(df.date.iloc[0])
        end = end_date.strftime("%Y-%m-%d")
        start_date = end_date - dt.timedelta(days=N)
        start = start_date.strftime("%Y-%m-%d")
        # create the price range dataframe
        try:
            if not isinstance(start, str) or not isinstance(end, str):
                raise ValueError(f"start and end must be strings.")
            price_range = ohlcv.price_range(start,end)
        except ValueError as e:
            raise ValueError(f"Failed to create price range dataframe: {e}")

        price_range = price_range.iloc[-1::-1]
        price_range.reset_index(drop=True,inplace=True)

        object.__setattr__(self,'df',df)
        object.__setattr__(self,'df_close',df_close)
        object.__setattr__(self, 'price_range', price_range)
        object.__setattr__(self, 'ohlcv', ohlcv)
        object.__setattr__(self, 'days', days)
        object.__setattr__(self, 'N', N)
        object.__setattr__(self,'start_date',start_date)
        object.__setattr__(self,'end_date',end_date)
        object.__setattr__(self, 'start', start)
        object.__setattr__(self, 'end', end)


    def rsi(self):
        """
        Relative Strength Index (RSI) is a measure of the strength of a security's price movement.
        If it is above 70, the security is overbought. If it is below 30, the security is oversold.
        Used as a core indicator in technical analysis.
        RS = mean of the up days / mean of the down days
        RSI = 100 - (100 / (1 + RS))
        """
        price_range = self.price_range

        closes = price_range.loc[:, "close"].tail(self.N).dropna().reset_index(drop=True)
        if len(closes) < 2:
            raise ValueError("RSI requires at least two closing prices.")

        deltas = closes.diff().dropna()
        gains = deltas.clip(lower=0)
        losses = -deltas.clip(upper=0)

        mean_u = gains.mean()
        mean_d = losses.mean()

        if mean_d == 0:
            if mean_u == 0:
                return 50.0
            return 100.0

        RS = mean_u / mean_d
        RSI = 100 - (100 / (1 + RS))

        return RSI

    def mfi(self):
        """
        Money Flow Index (MFI) is an oscillator that measures the money flow into a security. It calculates
        the typical price at t times volume at t. It then compares the positive and negative money flow
        to determine the money flow ratio. MFI > 80 is overbought, MFI < 20 is oversold.
        Typical Price = (high_t + low_t + close_t) / 3
        Money Flow = Typical Price * Volume
        Money Ratio = positive_MF / negative_MF
        MFI = 100 - (100 / (1 + money_ratio))
        """
        N = self.N
        price_range = self.price_range

        # create price series objects
        high = price_range.loc[:,'high']
        low = price_range.loc[:,'low']
        close = price_range.loc[:,'close']
        volume = price_range.loc[:,'volume']

        pos_mf = 0
        neg_mf = 0

        TP = (high + low + close) / 3
        money_flow = TP * volume
        for i,now in enumerate(money_flow[:-1]):
            try:
                prev = money_flow.iloc[i + 1]
            except IndexError:
                break
            if now > prev:
                pos_mf += now
            elif now < prev:
                neg_mf += now
            else:
                continue
        money_ratio = pos_mf / neg_mf
        MFI = 100 - (100 / (1 + money_ratio))
        return MFI

    def stoch(self,smooth:int=3):
        """
        Stochastic Oscillator is a momentum indicator that compares a security's closing price to its price
        range over a set period of time. It can measure the velocity of how a price is moving. It takes the
        average of the (SP - low / high - low) x 100 for the period. That is then used to calculate the average
        over a defined period. It uses SMA. And it uses a second, shorter period to smooth the signal.
        When %D is in extreme (20>%D>80) and diverging from the price, this is a signal for reversal/entry/exit
        moments. The signal takes place when %K crosses %D.
        """
        if not smooth or smooth > self.N or smooth <= 0:
            raise ValueError(f"smooth must be a positive integer less than or equal to N.")

        N = self.N
        price_range = self.price_range

        pct_D = 0

        for s in range(smooth):
            high = price_range.high.iloc[s:]
            low = price_range.low.iloc[s:]
            close = price_range.close.iloc[s]
            hh, ll = high.max(), low.min()
            pct_K_0 = 100 * ((close - ll) / (hh - ll))
            pct_D += pct_K_0

        pct_D = pct_D / smooth

        return (pct_D, pct_K_0)

    def cmf(self):
        """
        Chaikin Money Flow indicator
        Calculates the hi and low near the close and the difference between the two in one observation.
        The result is an oscillator that measures the momentum of a security's price.
        """
        N = self.N
        price_range = self.price_range

        close = price_range.loc[:,'close']
        high = price_range.loc[:,'high']
        low = price_range.loc[:,'low']
        volume = price_range.loc[:,'volume']

        CLV = ((close - low) - (high - close)) / (high - low)
        numerator = CLV * volume
        numerator = numerator.sum()
        denominator = volume.sum()
        CMF = numerator / denominator

        return CMF

    def cmo(self):
        """
        Chande Mommentum Oscillator (CMO) is a momentum oscillator that measures the speed and change of price.
        Calculate the Curr_P v Prev_P. Keep a tally of the positive and negative changes. Sum and subtract the
        positive and negative changes. Divide by the sum of the absolute values of the positive and negative
        changes. CMO of +50 is overbought, -50 is oversold, and divergence from price is a signal for a reversal.
        """
        N = self.N
        price_range = self.price_range

        pos_change = 0
        neg_change = 0
        for c in range(N-1):
            try:
                curr_p = price_range.close.iloc[c]
                prev_p = price_range.close.iloc[c + 1]
            except IndexError:
                break
            if curr_p > prev_p:
                pos_change += (curr_p - prev_p)
            elif curr_p < prev_p:
                neg_change += (prev_p - curr_p)
        if pos_change + neg_change == 0:
            return 0
        cmo = ((pos_change - neg_change) / (pos_change + neg_change)) * 100
        return cmo

    def williams_r(self):
        """
        Williams %R is a momentum indicator that measures overbought or oversold conditions.
        It is calculated by taking the high, low, and close of the last n periods and then
        calculating the %R. %R is then plotted on a scale of -100 to 0, with -100 being the lowest
        and 0 being the highest.
        The %R is usually used for longer term trends. Very volatile in short term ranges.
        %R = (Highest High - Close) / (Highest High - Lowest Low) * -100
        """

        N = self.N
        price_range = self.price_range

        HH = price_range.loc[:,'high'].max()
        LL = price_range.loc[:,'low'].min()
        close = price_range.close.iloc[0]

        williams_r = ((HH - close) / (HH - LL)) * (-100)

        return williams_r

    def adx(self):
        """
        Average Directional Index (ADX) is a technical indicator used to measure the strength of
        a trend. Its primary use was designed for the commodity's market and intraday price trends.
        It can be used in conjunction with other indicators to better forecast a trend.
        The ADX is calculated using the number of 'up moves' and 'down moves' over a period of time.
        The 'up moves' and 'down moves' are when the high of today is higher than yesterday, and the low
        of today is lower than yesterday's. That number is added to all the other up and down moves over
        a period. A smoothed average is taken from the up and down moves (+DM,-DM). The smoothed average
        is then divided by the Average True Range (ATR) for the same period. That is down over other
        prior periods, and the smoothed average of those numbers (+DI,-DI) is then used to calculate the
        ADX. A strong up trend is considered so when ADX > 20, and weak when ADX < 20.
        """
        from analytics.MovingAverages import MovingAverageSignals as MAS

        N = self.N
        price_range = self.price_range
        start = self.start
        pos_DI = 0
        neg_DI = 0

        for i in range(N-1):
            pos_DM = 0
            neg_DM = 0
            a = 1 / N
            prev_up = 0
            prev_down = 0

            for j in range(N-1):
                t_low = price_range.iloc[j + i].low
                t_m_1_low = price_range.iloc[j + i + 1].low
                t_high = price_range.iloc[j + i].high
                t_m_1_high = price_range.iloc[j + i + 1].high
                upmove = (t_high - t_m_1_high)
                downmove = (t_m_1_low - t_low)

                if upmove > 0 and upmove > downmove:
                    pos_DM += upmove
                    neg_DM += 0
                elif downmove > 0 and downmove > upmove:
                    neg_DM += downmove
                    pos_DM += 0
                else:
                    neg_DM += 0
                    pos_DM += 0

            pos_DI = (pos_DM / (N-1))
            neg_DI = (neg_DM / (N-1))

            atr = MAS.avg_true_return(self.ticker,start=start,period=N)

            pos_DI += (100 * (pos_DI / atr))
            neg_DI += (100 * (neg_DI / atr))

        pos_DI = pos_DI / (N-1)
        neg_DI = neg_DI / (N-1)

        adx = 100 * (abs(pos_DI - neg_DI)) / (pos_DI + neg_DI)

        return adx

    def aroon_osc(self):
        """
        Aroon Oscillator is a technical indicator that measures a securities vigor and trend. It can
        shows how a security is either going to reverse, or is going in a given direction.
        Aroon Up = ( (N - DH) / N ) * 100
        Aroon Down = ( (N - DL) / N ) * 100
        Aroon Oscillator = Aroon Up - Aroon Down
        The value lies between -100 and 100. A value of 100 indicates a strong uptrend, and -100 indicates
        a strong downtrend. The Aroon Oscillator was originally developed for the commodities market, and
        daily price trends in order to look for reversals, entry and exit points.
        """
        N = self.N
        price_range = self.price_range

        h_max = price_range.high.iloc[:N].max()
        h_loc = price_range[price_range.high == h_max].index[0]
        DH = len(price_range.loc[:h_loc]) - 1
        l_max = price_range.low.iloc[:N].min()
        l_loc = price_range[price_range.low == l_max].index[0]
        DL = len(price_range.loc[:l_loc]) - 1

        Aroon_Up = ((N - DH) / N) * 100
        Aroon_Down = ((N - DL) / N) * 100

        ao = Aroon_Up - Aroon_Down

        return ao

    def accum_dist(self):
        """
        Accumulation/Distribution Line (ADL) is a technical indicator that measures the cumulative
        flow of money into and out of a security. It is calculated by taking the difference between
        the current close and the previous close, and multiplying it by the volume. The ADL is
        returned as a value which could be -1x10^10 to 1x10^10 (i.e. -billions to +billions as the
        volume traded in a day or weekcan be in the billions+).
        It's also returned as the ADL for the current day. Use accum_dist_df() to get the ADL for
        each day over the given number of days.
        """
        N = self.N
        price_range = self.price_range

        c = price_range.close.iloc[0]
        prev_c = price_range.close.iloc[1]

        accum_dist = (c - prev_c) * price_range.volume.iloc[0]

        return accum_dist

    def accum_dist_df(self) -> pd.Series:
        """
        This function will take the same formula used in accum_dist(), and apply it across a dataframe.
        The function will return a dataframe with the ADL for each row. It is calculated by taking the
        difference between the current close and the previous close, and multiplying it by the volume.
        If the dataframe entered is derived from daily data or 1 min data, the function will return the
        ADL as a pd.Series which can then be further aggregated to get AD values for the self._period.
        """
        N = self.N
        price_range = self.price_range
        series = np.zeros(len(price_range.index),index=price_range.index)
        for i in range(N-1):
            c = price_range.close.iloc[i]
            prev_c = price_range.close.iloc[i-1]
            v = price_range.volume.iloc[i]

            accum_dist = (c - prev_c) * v
            series.iloc[i] = accum_dist

        return pd.Series(series,index=price_range.index,name='accumulatedDistribution')

    def obv(self) -> pd.Series:
        """
        On Balance Volume (OBV) is a technical indicator that measures the cumulative flow of money into
        and out of a security. It is calculated by taking the difference between the current close and the
        previous close, and multiplying it by the volume. The OBV is then plotted on a scale of 0 to 100.
        """
        N = self.N
        price_range = self.price_range

        series = np.zeros(len(price_range),index=price_range.index)
        OBV = 0

        for i in range(len(price_range) - 1):
            prev_close = price_range.close.iloc[i + 1]
            if price_range.close.iloc[i] > prev_close:
                OBV += price_range.volume.iloc[i]
                series[i] = OBV
            elif price_range.close.iloc[i] < prev_close:
                OBV -= price_range.volume.iloc[i]
                series[i] = OBV
            else:
                OBV += 0
                series[i] = OBV

        return pd.Series(series,index=price_range.index,name='onBalanceVolume')

    def bollinger_bands(self):
        """
        Bollinger Bands are a technical indicator that measures the volatility of a security's price.
        It is calculated by taking the average of the last 20 days of prices, and then adding and subtracting
        two standard deviations from the average. The Bollinger Bands are then plotted on a chart, and can
        be used to identify overbought and oversold conditions.
        """
        days = 20 if self.N < 20 else self.N
        start_date = self.end_date - dt.timedelta(days=days)
        start = start_date.strftime("%Y-%m-%d")
        end = self.end
        price_range = self.ochlv.price_range(start,end)

        MA = price_range.loc[:, 'close'].mean()
        std = price_range.loc[:, 'close'].std()

        upper_band = MA + (2 * std)
        lower_band = MA - (2 * std)

        return (MA, upper_band, lower_band)

    def candlestick(self) -> pd.DataFrame:
        """
        Candlestick patterns are a technical indicator that measures the strength of a security's price.
        It is calculated by taking the open, high, low, and close of a security's price. The candlestick
        patterns are then plotted on a chart, either singularly, or as an over/underlaying chart pattern.
        """
        df = self.df.copy()

        c = df.loc[:,'close']
        h = df.loc[:,'high']
        l = df.loc[:,'low']
        m = (h + l + c) / 3

        df.loc[:,'candleStick'] = m
        return df

    def impulseBB(self):
        """
        Impulse Bands are a technical indicator that measures the volatility of a security's price.
        It is calculated by taking the average of the last 20 days of prices, and then adding and subtracting
        two standard deviations from the average. The Impulse Bands are then plotted on a chart, and can
        be used to identify overbought and oversold conditions.
        """
        from analytics.MovingAverages import MovingAverageSignals as MAS

        # set the price range to the minumum 20 day window size
        period = self.N if self.N >= 20 else 20
        start = self.end_date = dt.timedelta(days=period)
        start = start.strftime('%Y-%m-%d')
        # create the new price_range dataframe
        df = self.ohlcv.price_range(start,self.end)

        if df is None or df.empty:
            return pd.DataFrame()
        # create the value objects
        raw_close = df['close'].iloc[:-1] - df['close'].shift(1).abs()
        atr = MAS.avg_true_return(self.ticker,start=self.start,period=period)

        raw_impulse = raw_close / atr
        raw_impulse.replace([np.inf, -np.inf], np.nan, inplace=True)

        raw_arr = raw_impulse.to_numpy()
        decayed_arr = np.zeros(len(raw_arr))
        df['ATR'] = atr
        df['baseline'] = df.close.ewm(span=period, adjust=False).mean()

        for i in range(1,len(raw_arr)):
            # momentum value
            current_raw = abs(raw_arr[i])
            # prior decay
            prior_decay = decayed_arr[i-1] * (1 - .1)
            decayed_arr[i] = max(prior_decay,current_raw)

        decayed_imp = pd.Series(decayed_arr, index=raw_impulse.index)
        df['decayed_impulse'] = decayed_imp
        # Assume a standard normalization cap (Max Expected Impulse) of 5.0 ATRs
        max_expected_imp = 5.0
        # Bound the ratio between 0 and 1 to prevent negative multipliers during massive spikes
        imp_ratio = (df["decayed_impulse"] / max_expected_imp).clip(0, 1)
        df["adaptive_multiplier"] = 2.5 * (1 - imp_ratio)

        df["upper_band"] = df["baseline"] + (df["adaptive_multiplier"] * df["ATR"])
        df["lower_band"] = df["baseline"] - (df["adaptive_multiplier"] * df["ATR"])

        return df['date','close','upper_band','lower_band','decayed_impulse','adaptive_multiplier','baseline','ATR']

    def fibonacci_pct(self):
        """
        Fibonacci Pct is a technical indicator that measures the difference between a security's
        price and its average price. It is calculated by taking the difference between the current price and the
        average price, and then dividing that by the average deviation. The principal relies on the fact that
        Fibanocci sequences naturally occur in percentages of price movements when prices move in a certain way.
        When they coincide with a fibonacci number at a certain point, it is a signal. Those points are
        23.6%,38.2%, 50%, 61.8%, 78.6%, 100%, 127.2%, 161.8%, 261.8%....
        """
        _df = self._df.copy()

        fib_pct = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.618]

        price = _df.close.iloc[self._period]
        up_level = [price * (1 + i) for i in fib_pct]
        down_level = [price * (1 - i) for i in fib_pct]
        max_price = _df.iloc[:self._period].close.max()
        min_price = _df.iloc[:self._period].close.min()
        price_rng = max_price - min_price

        fib_levels = []

        for i in range(len(fib_pct)):
            level = up_level[i] - max_price - (fib_pct[i] * price_rng)
            fib_levels.append(level)

        return tuple(fib_levels)

    def rel_vigor_index(self):
        """
        Relative Vigor Index (RVI) measures the strength of a trend by contrasting a security's closing
        price with its traded price range. This is then smoothed w/ an SMA.
        NUMERATOR = (CLOSE - OPEN) / (HIGH - LOW)
        DENOMINATOR = (CLOSE - OPEN) / (HIGH - LOW)
        RVI = SMA(NUMERATOR) / SMA(DENOMINATOR)
        Signal_Line = RVI + ((2 x i) + (2 + j) + k)/6
        """
        _df = self._df.copy()
        rvi = {}
        period = list(range(self._period))

        for x in [0, 1, 2]:
            NUMERATOR = 0
            DENOMINATOR = 0
            for y in period:
                a_c = _df.close.iloc[int(y + x)]
                a_o = _df.open.iloc[int(y + x)]
                b_c = _df.close.iloc[int(y + x + 1)]
                b_o = _df.open.iloc[int(y + x + 1)]
                c_c = _df.close.iloc[int(y + x + 2)]
                c_o = _df.open.iloc[int(y + x + 2)]
                d_c = _df.close.iloc[int(y + x + 3)]
                d_o = _df.open.iloc[int(y + x + 3)]
                e_h = _df.high.iloc[int(y + x)]
                e_l = _df.low.iloc[int(y + x)]
                f_h = _df.high.iloc[int(y + x + 1)]
                f_l = _df.low.iloc[int(y + x + 1)]
                g_h = _df.high.iloc[int(y + x + 2)]
                g_l = _df.low.iloc[int(y + x + 2)]
                h_h = _df.high.iloc[int(y + x + 3)]
                h_l = _df.low.iloc[int(y + x + 3)]

                a = a_c - a_o
                b = b_c - b_o
                c = c_c - c_o
                d = d_c - d_o
                e = e_h - e_l
                f = f_h - f_l
                g = g_h - g_l
                h = h_h - h_l

                NUMERATOR += (a + (2 * b) + (2 * c) + d) / 6
                DENOMINATOR += (e + (2 * f) + (2 * g) + h) / 6

            SMA_NUM = NUMERATOR / 20
            SMA_DEN = DENOMINATOR / 20

            RVI = SMA_NUM / SMA_DEN
            rvi[int(x)] = RVI

        Signal_Line = RVI + ((2 * rvi[0]) + (2 * rvi[1]) + rvi[2]) / 6
        return rvi[0], Signal_Line

    def roc(self):
        """
        Rate of Change (ROC) measures the percent of change in a security's price over a period of time.
        It is considered a momentum oscillator. ROC can be used in conjunction with other indicators and helps
        to identify a security's momentum in a given direction and indicating possible reversals.
        ROC = ((Current Price - Closing Price N periods ago) / Closing Price N periods ago) * 100
        """
        _df = self._df.copy()

        c = _df.close.iloc[0]
        c_n = _df.close.iloc[self._period]

        ROC = ((c_n - c) / c) * 100

        return ROC
