# Python 3.13 UTF-8
"""
Benjamin Graham style investment criteria.

The value classes return calculated historical values. The investor classes
convert those values into pass/fail criteria. Graham's earnings growth test is
based on per-share earnings, not book value: compare the latest 3-year average
EPS with the 3-year average EPS from the beginning of the lookback period.
"""

from dataclasses import dataclass
import datetime as dt

import numpy as np
import pandas as pd

from data_access.CompanyDetails import CompanyDetails as CD
from data_access.PipelineETL import FinancialData as FD


DEFENSIVE_MIN_REVENUE = 500_000_000
DEFENSIVE_UTILITY_MIN_REVENUE = 250_000_000
DEFENSIVE_CURRENT_RATIO_MIN = 2.0
DEFENSIVE_UTILITY_MAX_DEBT_TO_BOOK_EQUITY = 2.0
DEFENSIVE_EPS_GROWTH_MIN = 1 / 3
DEFENSIVE_EPS_CAGR_MIN = 0.03
DEFENSIVE_MAX_PE = 15.0
DEFENSIVE_MAX_PRICE_TO_BOOK = 1.5

ENTERPRISING_CURRENT_RATIO_MIN = 1.5
ENTERPRISING_MAX_DEBT_TO_NET_CURRENT_ASSETS = 1.1
ENTERPRISING_MAX_PRICE_TO_TANGIBLE_BOOK = 1.2


def defensive_min_revenue_for_sector(sector: str | None) -> int:
    """Return the documented Defensive revenue floor for a sector."""
    normalized_sector = (sector or "").strip().upper()
    if normalized_sector in {"UTILITY", "UTILITIES"}:
        return DEFENSIVE_UTILITY_MIN_REVENUE
    return DEFENSIVE_MIN_REVENUE


@dataclass(frozen=False)
class BaseValueConfigs:
    ticker: str
    period_range: int = 10


@dataclass(frozen=False)
class Dates:
    """
    Return start/end dates for a ticker over a period range.
    """

    def __init__(self, ticker: str, period_range: int = 7):
        self.config = BaseValueConfigs(ticker=ticker, period_range=period_range)

        company_details = CD()
        if not company_details.get_details(ticker=self.config.ticker):
            raise ValueError(f"Ticker {self.config.ticker} not found in the database.")
        self.company_details = company_details

        self.a_date = self.company_details.get_latest_annual_fiscal_date(
            ticker=self.config.ticker
        )
        self.q_date = self.company_details.get_latest_quarterly_fiscal_date(
            ticker=self.config.ticker
        )
        if not self.a_date or not self.q_date:
            raise ValueError(
                f"Could not retrieve financial dates for ticker {self.config.ticker}"
            )
        self.iso_and_datetime_start_stop_dates = {
            "str_annual": self.a_date,
            "str_last_quarterly": self.q_date,
            "dt_annual": dt.date.fromisoformat(self.a_date),
            "dt_quarterly": dt.date.fromisoformat(self.q_date),
        }


    def start_end_dates(self) -> dict:
        dates = self.iso_and_datetime_start_stop_dates
        current = dates.get("dt_annual")
        start_date = dt.date(
            current.year - self.config.period_range,
            current.month,
            current.day,
        )
        return {"start": start_date, "end": dates.get("dt_annual")}


    def start_end_dates_ranges(self) -> dict:
        dates = self.iso_and_datetime_start_stop_dates
        current_year = dates.get("dt_annual").year
        start_year = current_year - self.config.period_range

        if start_year < 1900:
            raise ValueError(
                f"Start year {start_year} is too early. "
                f"Please check ticker {self.config.ticker}"
            )
        return {
            "start": np.arange(start=start_year - 2, stop=start_year + 1, step=1),
            "end": np.arange(start=current_year - 2, stop=current_year + 1, step=1),
        }


def false_array(shape, index=None):
    idx = index if index is not None else np.arange(shape)
    return pd.Series(np.zeros(shape), dtype=bool, index=idx)


def _nullable_comparison(
    values: pd.Series,
    comparison,
    name: str,
) -> pd.Series:
    """Evaluate a criterion without treating a missing value as a failure."""
    result = comparison(values).astype("boolean")
    result = result.mask(values.isna(), pd.NA)
    result.name = name
    return result


def _rolling_all_positive(
    values: pd.Series,
    period: int,
    name: str,
) -> pd.Series:
    result = pd.Series(pd.NA, index=values.index, dtype="boolean", name=name)
    for idx in range(len(values)):
        window = values.iloc[idx:idx + period]
        if len(window) < period or window.isna().any():
            continue
        result.iloc[idx] = bool((window > 0).all())
    return result


class _GrahamCriteriaValueBase:
    """
    Shared helpers for Graham criteria classes that return calculated values.
    """

    def __init__(self, ticker: str, period_range: int, min_years: int):
        if not isinstance(ticker, str):
            raise ValueError(f"Argument {ticker} must be a string")
        ticker = ticker.upper()

        fd = FD(ticker)
        df = fd.create_value_dataframe(min_years=min_years)
        if df is None or df.empty:
            reason = getattr(fd, "last_error", None)
            if reason:
                raise ValueError(
                    f"Unable to build value dataframe for ticker {ticker}: {reason}"
                )
            raise ValueError(f"Dataframe for ticker {ticker} is empty or None")

        self._init_from_dataframe(ticker, period_range, min_years, df)


    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        ticker: str = "TEST",
        period_range: int | None = None,
        min_years: int | None = None,
    ):
        obj = cls.__new__(cls)
        obj._init_from_dataframe(
            ticker=ticker.upper(),
            period_range=period_range or cls.default_period_range,
            min_years=min_years or cls.default_min_years,
            df=df,
        )
        return obj


    def _init_from_dataframe(
        self,
        ticker: str,
        period_range: int,
        min_years: int,
        df: pd.DataFrame,
    ) -> None:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("df must be a non-empty pandas DataFrame")
        df = df.copy()
        if "fiscalDateEnding" not in df.columns:
            raise KeyError("fiscalDateEnding column is required")
        df["fiscalDateEnding"] = pd.to_datetime(
            df["fiscalDateEnding"],
            errors="coerce",
        )
        df = df.dropna(subset=["fiscalDateEnding"])
        df = df.sort_values("fiscalDateEnding", ascending=False).reset_index(drop=True)
        if df.empty:
            raise ValueError("df has no valid fiscalDateEnding values")

        object.__setattr__(self, "_df", df)
        object.__setattr__(
            self,
            "config",
            BaseValueConfigs(ticker=ticker, period_range=period_range),
        )
        object.__setattr__(self, "min_years", min_years)


    @staticmethod
    def _safe_divide(numerator, denominator, name: str) -> pd.Series:
        numerator = pd.Series(numerator).astype(float)
        denominator = pd.Series(denominator).astype(float).replace(0, np.nan)
        result = numerator / denominator
        result.name = name
        return result.replace([np.inf, -np.inf], np.nan)


    def _series(self, column: str, name: str | None = None) -> pd.Series:
        if column not in self._df.columns:
            series = pd.Series(np.nan, index=self._df.index, dtype=float)
        else:
            series = pd.to_numeric(self._df.loc[:, column], errors="coerce")
        series.name = name or column
        return series.replace([np.inf, -np.inf], np.nan)


    def _date_row(self, date: str | None = None) -> pd.Series:
        fiscal_dates = pd.to_datetime(self._df["fiscalDateEnding"], errors="coerce")
        if fiscal_dates.isna().all():
            raise ValueError("No valid fiscalDateEnding values were found")

        if date is None:
            return self._df.loc[fiscal_dates.idxmax()]

        requested = pd.to_datetime(date)
        exact_match = fiscal_dates == requested
        if exact_match.any():
            return self._df.loc[exact_match].iloc[0]

        prior_dates = fiscal_dates[fiscal_dates <= requested]
        if not prior_dates.empty:
            return self._df.loc[prior_dates.idxmax()]

        return self._df.loc[fiscal_dates.idxmin()]


    def latest_annual(self) -> dict:
        return self.get_by_date()


    def _value_at_date(self, series: pd.Series, date: str | None = None) -> float | int:
        row = self._date_row(date)
        value = series.loc[row.name]
        if pd.isna(value):
            return np.nan
        value = float(value)
        if value.is_integer():
            return int(value)
        return value


    def _eps(self) -> pd.Series:
        reported_eps = self._series("reportedEPS")
        if not reported_eps.isna().all():
            reported_eps.name = "reportedEPS"
            return reported_eps
        eps = self._safe_divide(
            self._series("netIncome"),
            self._series("commonStockSharesOutstanding"),
            "reportedEPS",
        )
        return eps


    def _rolling_current_3yr_average_eps(self) -> pd.Series:
        eps = self._eps()
        avg = pd.Series(np.nan, index=self._df.index, dtype=float)
        for idx in range(len(eps)):
            if idx + 3 <= len(eps):
                avg.iloc[idx] = eps.iloc[idx : idx + 3].mean()
        avg.name = "currentThreeYearAverageEPS"
        return avg


    def _book_value_per_share(self) -> pd.Series:
        bvps = self._safe_divide(
            self._series("totalAssets") - self._series("totalLiabilities"),
            self._series("commonStockSharesOutstanding"),
            "bookValuePerShare",
        )
        return bvps


    def _optional_financial_sheet_series(self, column: str) -> pd.Series:
        # Optional balance-sheet fields should not erase tangible-book-value
        # calculations when a source omits the column.
        if column not in self._df.columns:
            return pd.Series(0.0, index=self._df.index, dtype=float, name=column)
        series = self._series(column)
        return series.fillna(0.0)


    def _tangible_book_value_per_share(self) -> pd.Series:
        _TA = self._series("totalAssets")
        _TL = self._series("totalLiabilities")
        _IA = self._optional_financial_sheet_series("intangibleAssets")
        _GW = self._optional_financial_sheet_series("goodwill")
        _PS = self._optional_financial_sheet_series("preferredStock")
        tbv = _TA - _TL - _IA - _GW - _PS
        return self._safe_divide(
            tbv,
            self._series("commonStockSharesOutstanding"),
            "tangibleBookValuePerShare",
        )


    def _net_current_assets(self) -> pd.Series:
        nca = self._series("totalCurrentAssets") - self._series(
            "totalCurrentLiabilities"
        )
        nca.name = "netCurrentAssets"
        return nca


    def net_current_asset_value(self) -> pd.Series:
        _CA = self._series('totalCurrentAssets').fillna(0)
        _TL = self._series("totalLiabilities").fillna(0)
        _PS = self._optional_financial_sheet_series("preferredStock")
        _PS = _PS.fillna(0)

        nca = _CA - _TL - _PS
        return self._safe_divide(
            nca,
            self._series("commonStockSharesOutstanding").replace(0,np.na),
            "netCurrentAssetValue",
        )


    def net_current_asset_value_margin_of_safety(self) -> pd.Series:
        ncav = self.net_current_asset_value()
        current_share_price = self._series("currentSharePrice")

        return self._safe_divide(
            ncav,
            current_share_price,
            "netCurrentAssetValueMarginOfSafety",
        )


class DefensiveInvestorCriteriaValues(_GrahamCriteriaValueBase):
    """
    Defensive Graham criteria as calculated values.
    """

    default_period_range = 10
    default_min_years = 10

    def __init__(self, ticker: str, period_range: int = 10, min_years: int = 10):
        if period_range < 10:
            raise ValueError(
                f"period_range must be greater than or equal to 10. "
                f"Received {period_range}"
            )
        if not isinstance(min_years, int) or min_years < 10:
            raise ValueError(
                f"min_years must be an integer greater than or equal to 10. "
                f"Received {min_years}"
            )
        super().__init__(ticker=ticker, period_range=period_range, min_years=min_years)


    @property
    def graham_number(self) -> pd.Series:
        avg_eps = self._rolling_current_3yr_average_eps()
        bvps = self._book_value_per_share()
        product = 22.5 * avg_eps * bvps
        product = product.where(product > 0)
        gn = product.pow(0.5)
        gn.name = "grahamNumber"
        return gn.replace([np.inf, -np.inf], np.nan)


    def total_sales_services(self) -> pd.Series:
        return self._series("totalRevenue", "totalSalesServices")


    def curr_assets_2x_curr_liab(self) -> pd.Series:
        return self._safe_divide(
            self._series("totalCurrentAssets"),
            self._series("totalCurrentLiabilities"),
            "currentAssets200pctCurrentLiabilities",
        )


    def long_debt_to_curr_assets(self) -> pd.Series:
        return self._safe_divide(
            self._series("longTermDebt"),
            self._net_current_assets(),
            "longTermDebtToNetCurrentAssets",
        )


    def long_term_debt_to_book_equity(self) -> pd.Series:
        book_equity = self._series("totalAssets") - self._series(
            "totalLiabilities"
        )
        return self._safe_divide(
            self._series("longTermDebt"),
            book_equity,
            "longTermDebtToBookEquity",
        )


    def pos_earnings(self, period: int = 10) -> pd.Series:
        earnings = self._df['netIncome']
        earnings.name = "positiveEarnings10yr"
        return earnings

    def divpayments(self) -> pd.Series:
        return self._series(
            "dividendPayoutCommonStock",
            "dividendPayoutCommonStock",
        )


    def common_stock_dividend_paid(self) -> pd.Series:
        """Return fiscal-year payment status from adjusted market history."""
        return self._series(
            "commonStockDividendPaid",
            "commonStockDividendPaid",
        )


    def average_dividend_payments(self, period: int = 20) -> pd.Series:
        dividends = self.divpayments()
        average = pd.Series(np.nan, index=self._df.index, dtype=float)
        for idx in range(len(dividends)):
            window = dividends.iloc[idx:idx + period]
            if len(window) < period or window.isna().any():
                continue
            average.iloc[idx] = window.mean()
        average.name = "averageDividendPayments20yr"
        return average


    def eps_growth_10yr(self) -> pd.Series:
        """
        Return total EPS growth from the beginning to the current lookback.

        The growth basis is the current 3-year average EPS compared with the
        beginning 3-year average EPS from the lookback window.
        """
        eps = self._eps()
        lookback = min(self.min_years, len(self._df))
        growth = pd.Series(np.nan, index=self._df.index, dtype=float)
        if lookback < 6:
            growth.name = "epsGrowth10yr"
            return growth

        for idx in range(len(eps)):
            if idx + lookback > len(eps):
                continue
            current_avg = eps.iloc[idx:idx + 3].mean()
            beginning_avg = eps.iloc[idx + lookback - 3:idx + lookback].mean()
            if pd.isna(current_avg) or pd.isna(beginning_avg) or beginning_avg <= 0:
                continue
            growth.iloc[idx] = (current_avg / beginning_avg) - 1
        growth.name = "epsGrowth10yr"
        return growth.replace([np.inf, -np.inf], np.nan)


    def eps_3pct_cagr_10yr(self) -> pd.Series:
        total_growth = self.eps_growth_10yr()
        lookback_years = max(min(self.min_years, len(self._df)) - 1, 1)
        cagr = ((1 + total_growth).pow(1 / lookback_years)) - 1
        cagr.name = "epsGrowth33pct10yr"
        return cagr.replace([np.inf, -np.inf], np.nan)


    def eps_3yr_average_to_10yr_previous_eps_ratio(self) -> pd.Series:
        ratio = self.eps_growth_10yr() + 1
        ratio.name = "eps3yrAverageTo10yrPreviousEPSRatio"
        return ratio.replace([np.inf, -np.inf], np.nan)


    def price_15x_EPS(self) -> pd.Series:
        return self._safe_divide(
            self._series("closingSharePrice"),
            self._rolling_current_3yr_average_eps(),
            "price15xEarningsPerShare3yrAverage",
        )


    def price_150pct_BV(self) -> pd.Series:
        return self._safe_divide(
            self._series("closingSharePrice"),
            self._book_value_per_share(),
            "price150pctBookValue",
        )


    def defensive_margin_of_safety(self) -> pd.Series:
        return self._safe_divide(
            self.graham_number,
            self._series("closingSharePrice"),
            "defensiveMarginOfSafety",
        )


    def get_by_date(self, date: str | None = None) -> dict:
        row = self._date_row(date)
        return {
            "ticker": self.config.ticker,
            "fiscalDateEnding": row.get("fiscalDateEnding").strftime("%Y-%m-%d"),
            "totalSalesServices": self._value_at_date(self.total_sales_services(), date),
            "currentAssets200pctCurrentLiabilities": self._value_at_date(self.curr_assets_2x_curr_liab(), date),
            "longTermDebtToNetCurrentAssets": self._value_at_date(
                self.long_debt_to_curr_assets(), date
            ),
            "longTermDebtToBookEquity": self._value_at_date(
                self.long_term_debt_to_book_equity(), date
            ),
            "positiveEarnings10yr": self._value_at_date(self.pos_earnings(), date),
            "dividendPayout": self._value_at_date(self.divpayments(), date),
            "averageDividendPayments20yr": self._value_at_date(
                self.average_dividend_payments(), date
            ),
            "currentThreeYearAverageEPS": self._value_at_date(
                self._rolling_current_3yr_average_eps(), date
            ),
            "epsGrowth33pct10yr": self._value_at_date(self.eps_3pct_cagr_10yr(), date),
            "eps3yrAverageTo10yrPreviousEPSRatio": self._value_at_date(
                self.eps_3yr_average_to_10yr_previous_eps_ratio(), date
            ),
            "price15xEarningsPerShare3yrAverage": self._value_at_date(
                self.price_15x_EPS(), date
            ),
            "bookValuePerShare": self._value_at_date(
                self._book_value_per_share(), date
            ),
            "price150pctBookValue": self._value_at_date(self.price_150pct_BV(), date),
            "grahamNumber": self._value_at_date(self.graham_number, date),
            "defensiveMarginOfSafety": self._value_at_date(
                self.defensive_margin_of_safety(), date
            ),
        }


class EnterprisingInvestorCriteriaValues(_GrahamCriteriaValueBase):
    """
    Enterprising Graham criteria as calculated values.
    """

    default_period_range = 5
    default_min_years = 5


    def __init__(self, ticker: str, period_range: int = 5, min_years: int = 5):
        if period_range < 5:
            raise ValueError(
                f"period_range must be greater than or equal to 5. "
                f"Received {period_range}"
            )
        super().__init__(ticker=ticker, period_range=period_range, min_years=min_years)


    @property
    def serenity_number(self) -> pd.Series:
        eps = self._rolling_current_3yr_average_eps()
        tbvps = self._tangible_book_value_per_share()
        product = 12 * eps * tbvps
        product = product.where(product > 0)
        sn = product.pow(0.5)
        sn.name = "serenityNumber"
        return sn.replace([np.inf, -np.inf], np.nan)


    def current_assets_150pct_long_term_debt(self) -> pd.Series:
        return self._safe_divide(
            self._net_current_assets(),
            self._series("longTermDebt"),
            "currentAssets150pctLongTermDebt",
        )


    def long_term_debt_110pct_net_current_assets(self) -> pd.Series:
        return self._safe_divide(
            self._series("longTermDebt"),
            self._net_current_assets(),
            "longTermDebt110pctNetCurrentAssets",
        )


    def some_current_dividend(self) -> pd.Series:
        return self._series(
            "dividendPayoutCommonStock",
            "dividendPayoutCommonStock",
        )


    def pos_earnings(self) -> pd.Series:
        earnings = self._series("netIncome")
        earnings.name = "positiveEarnings5yr"
        return earnings


    def earnings_growth_5yr(self) -> pd.Series:
        earnings = self._series("netIncome")
        series = pd.Series(np.nan, index=self._df.index, dtype=float)
        for idx in range(len(earnings)):
            prior_idx = idx + 5
            if prior_idx >= len(earnings):
                continue
            beginning_earnings = earnings.iloc[prior_idx]
            current_earnings = earnings.iloc[idx]
            if any(
                    (
                            pd.isna(beginning_earnings),
                            beginning_earnings <= 0,
                            pd.isna(current_earnings),
                            current_earnings <= 0
                    )
            ):
                continue
            series.iloc[idx] = (((current_earnings / beginning_earnings)**(.2)) - 1)
        series.name = "earningsGrowth5yr"
        return series.replace([np.inf, -np.inf], np.nan)


    def earnings_to_5yr_lookback_ratio(self) -> pd.Series:
        earnings = self._series("netIncome")
        ratio = pd.Series(np.nan, index=self._df.index, dtype=float)
        for idx in range(len(earnings)):
            prior_idx = idx + 5
            if prior_idx >= len(earnings):
                continue
            beginning_earnings = earnings.iloc[prior_idx]
            current_earnings = earnings.iloc[idx]
            if (
                pd.isna(current_earnings)
                or pd.isna(beginning_earnings)
                or beginning_earnings <= 0
            ):
                continue
            ratio.iloc[idx] = current_earnings / beginning_earnings
        ratio.name = "earningsTo5yrLookbackRatio"
        return ratio.replace([np.inf, -np.inf], np.nan)


    def price_120pct_tangible_assets(self) -> pd.Series:
        return self._safe_divide(
            self._series("closingSharePrice"),
            self._tangible_book_value_per_share(),
            "price120pctTangibleBook",
        )


    def enterprising_margin_of_safety(self) -> pd.Series:
        return self._safe_divide(
            self.serenity_number,
            self._series("closingSharePrice"),
            "enterprisingMarginOfSafety",
        )


    def get_by_date(self, date: str | None = None) -> dict:
        row = self._date_row(date)
        return {
            "ticker": self.config.ticker,
            "fiscalDateEnding": row.get("fiscalDateEnding").strftime("%Y-%m-%d"),
            "currentThreeYearAverageEPS": self._value_at_date(
                self._rolling_current_3yr_average_eps(), date
            ),
            "currentAssets150pctLongTermDebt": self._value_at_date(
                self.current_assets_150pct_long_term_debt(), date
            ),
            "longTermDebt110pctNetCurrentAssets": self._value_at_date(
                self.long_term_debt_110pct_net_current_assets(), date
            ),
            "positiveEarnings5yr": self._value_at_date(self.pos_earnings(), date),
            "dividendPayout": self._value_at_date(self.some_current_dividend(), date),
            "earningsGrowth5yr": self._value_at_date(
                self.earnings_growth_5yr(), date
            ),
            "earningsTo5yrLookbackRatio": self._value_at_date(
                self.earnings_to_5yr_lookback_ratio(), date
            ),
            "tangibleBookValuePerShare": self._value_at_date(
                self._tangible_book_value_per_share(), date
            ),
            "price120pctTangibleBook": self._value_at_date(
                self.price_120pct_tangible_assets(), date
            ),
            "serenityNumber": self._value_at_date(self.serenity_number, date),
            "enterprisingMarginOfSafety": self._value_at_date(
                self.enterprising_margin_of_safety(), date
            ),
        }


class DefensiveInvestor:
    """
    Defensive investor pass/fail criteria derived from calculated values.
    """

    def __init__(self, ticker: str, period_range: int = 10, min_years: int = 10):
        self.values = DefensiveInvestorCriteriaValues(
            ticker=ticker,
            period_range=period_range,
            min_years=min_years,
        )
        self.config = self.values.config
        self._df = self.values._df


    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        ticker: str = "TEST",
        period_range: int = 10,
        min_years: int = 10,
    ):
        obj = cls.__new__(cls)
        obj.values = DefensiveInvestorCriteriaValues.from_dataframe(
            df=df,
            ticker=ticker,
            period_range=period_range,
            min_years=min_years,
        )
        obj.config = obj.values.config
        obj._df = obj.values._df
        return obj


    @classmethod
    def from_values(cls, values: DefensiveInvestorCriteriaValues):
        obj = cls.__new__(cls)
        obj.values = values
        obj.config = values.config
        obj._df = values._df
        return obj


    @property
    def graham_number(self) -> pd.Series:
        return self.values.graham_number


    def total_sales_services(
        self,
        minimum_revenue: float = DEFENSIVE_MIN_REVENUE,
    ) -> pd.Series:
        """
        Company should meet the documented minimum annual revenue.

        Utilities use a lower threshold supplied by the service layer.
        """
        values = self.values.total_sales_services()
        return _nullable_comparison(
            values,
            lambda series: series >= minimum_revenue,
            "totalSalesServicesGteMinimum",
        )


    def curr_assets_2x_curr_liab(self) -> pd.Series:
        """
        Company should have current assets greater than or equal to twice its current liabilities.
        This is a measure of liquidity and financial stability.

        :return: True if current assets >= 2x liabilities, else False.
        """
        values = self.values.curr_assets_2x_curr_liab()
        return _nullable_comparison(
            values,
            lambda series: series >= DEFENSIVE_CURRENT_RATIO_MIN,
            "currentAssetsGte200pctCurrentLiabilities",
        )


    def long_debt_to_curr_assets(self) -> pd.Series:
        """
        Company should have long-term debt less than or equal to its net current assets.
        This is a measure of financial stability and solvency.

        :return: True if long-term debt <= net current assets, else False.
        """
        values = self.values.long_debt_to_curr_assets()
        return _nullable_comparison(
            values,
            lambda series: series <= 1.0,
            "longTermDebtLessThanNetCurrentAssets",
        )


    def utility_debt_to_book_equity(self) -> pd.Series:
        """Evaluate the Utility long-term-debt/book-equity limit."""
        values = self.values.long_term_debt_to_book_equity()
        return _nullable_comparison(
            values,
            lambda series: (
                series <= DEFENSIVE_UTILITY_MAX_DEBT_TO_BOOK_EQUITY
            ),
            "utilityDebtLte200pctBookEquity",
        )


    def pos_earnings(self, period: int = 10) -> pd.Series:
        """
        Company should have positive earnings for the past 10 years.
        This is a measure of profitability and financial health.

        :param period: Number of years to look back for positive earnings.
        :return: True if positive earnings for each year during the period given, else False.
        """
        return _rolling_all_positive(
            self.values.pos_earnings(),
            period,
            "positiveEarnings10yr",
        )


    def divpayments(self, period: int = 20) -> pd.Series:
        """
        Positive dividend payments for each year in the requested lookback.
        """
        return _rolling_all_positive(
            self.values.common_stock_dividend_paid(),
            period,
            "continuousDividendPayments20yr",
        )


    def eps_3yr_average_gte_33pct_10yr_previous(self) -> pd.Series:
        values = self.values.eps_3yr_average_to_10yr_previous_eps_ratio()
        return _nullable_comparison(
            values,
            lambda series: series >= 1 + DEFENSIVE_EPS_GROWTH_MIN,
            "eps3yrAverageGte33pct10yrPreviousEPS",
        )


    def eps_gte_3pct_cagr_10yr(self) -> pd.Series:
        """
        returns the eps rate compared to 33% growth since 10 years ago
        :return: True if eps growth rate is >= 33%, else False
        """
        values = self.values.eps_3pct_cagr_10yr()
        return _nullable_comparison(
            values,
            lambda series: series >= DEFENSIVE_EPS_CAGR_MIN,
            "epsGrowthGte33pct10yr",
        )


    def price_lte_15x_EPS(self) -> pd.Series:
        """
        Market price (without regards to a company's 'moat') should not be greater than 15x earnings per share
        :return: True if market price is <= 15x earnings per share, else False
        """
        values = self.values.price_15x_EPS()
        return _nullable_comparison(
            values,
            lambda series: series <= DEFENSIVE_MAX_PE,
            "priceLte15xEPS",
        )


    def price_lte_150pct_BV(self) -> pd.Series:
        """
        Market price (without regards to a company's 'moat') should not be greater than 1.5x book value
        :return: True if market price is <= 1.5x book value, else False
        """
        values = self.values.price_150pct_BV()
        return _nullable_comparison(
            values,
            lambda series: series <= DEFENSIVE_MAX_PRICE_TO_BOOK,
            "priceLte150pctBV",
        )


    def defensive_margin_of_safety(self) -> pd.Series:
        """
        Company's Graham Number divided by its current market price. A value greater than 1 means the market value
        is less than the company's intrinsic value, and, therefore, at a discount.
        :return: Graham Number / Current Market Price
        """
        return self.values.defensive_margin_of_safety()


    def defensive_investor(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "fiscalDateEnding": self._df.fiscalDateEnding,
                "grahamNumber": self.graham_number,
                "defensiveMarginOfSafety": self.defensive_margin_of_safety(),
                "closingSharePrice": self.values._series("closingSharePrice"),
            }
        )


    def criteria_dataframe(
        self,
        minimum_revenue: float = DEFENSIVE_MIN_REVENUE,
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "fiscalDateEnding": self._df.fiscalDateEnding,
                "totalSalesServicesGteMinimum": self.total_sales_services(
                    minimum_revenue
                ),
                "currentAssetsGte200pctCurrentLiabilities": self.curr_assets_2x_curr_liab(),
                "longTermDebtLessThanNetCurrentAssets": self.long_debt_to_curr_assets(),
                "utilityDebtLte200pctBookEquity": (
                    self.utility_debt_to_book_equity()
                ),
                "positiveEarnings10yr": self.pos_earnings(),
                "eps3yrAverageGte33pct10yrPreviousEPS": (
                    self.eps_3yr_average_gte_33pct_10yr_previous()
                ),
                "continuousDividendPayments20yr": self.divpayments(),
                "priceLte15xEPS": self.price_lte_15x_EPS(),
                "priceLte150pctBV": self.price_lte_150pct_BV(),
            }
        )

    def criteria_dict(
        self,
        minimum_revenue: float = DEFENSIVE_MIN_REVENUE,
    ):
        return {
                "fiscalDateEnding": self._df.fiscalDateEnding,
                "totalSalesServicesGteMinimum": self.total_sales_services(
                    minimum_revenue
                ),
                "currentAssetsGte200pctCurrentLiabilities": self.curr_assets_2x_curr_liab(),
                "longTermDebtLessThanNetCurrentAssets": self.long_debt_to_curr_assets(),
                "utilityDebtLte200pctBookEquity": (
                    self.utility_debt_to_book_equity()
                ),
                "positiveEarnings10yr": self.pos_earnings(),
                "eps3yrAverageGte33pct10yrPreviousEPS": (
                    self.eps_3yr_average_gte_33pct_10yr_previous()
                ),
                "continuousDividendPayments20yr": self.divpayments(),
                "priceLte15xEPS": self.price_lte_15x_EPS(),
                "priceLte150pctBV": self.price_lte_150pct_BV(),
            }


class EnterprisingInvestor:
    """
    Enterprising investor pass/fail criteria derived from calculated values.
    """

    def __init__(self, ticker: str, period_range: int = 5, min_years: int = 5):
        self.values = EnterprisingInvestorCriteriaValues(
            ticker=ticker,
            period_range=period_range,
            min_years=min_years,
        )
        self.config = self.values.config
        self._df = self.values._df


    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        ticker: str = "TEST",
        period_range: int = 5,
        min_years: int = 5,
    ):
        obj = cls.__new__(cls)
        obj.values = EnterprisingInvestorCriteriaValues.from_dataframe(
            df=df,
            ticker=ticker,
            period_range=period_range,
            min_years=min_years,
        )
        obj.config = obj.values.config
        obj._df = obj.values._df
        return obj


    @classmethod
    def from_values(cls, values: EnterprisingInvestorCriteriaValues):
        obj = cls.__new__(cls)
        obj.values = values
        obj.config = values.config
        obj._df = values._df
        return obj


    def serenity_number(self) -> pd.Series:
        """
        The intrinsic value of a company according to the parameters put forward in 'The Intelligent Investor'
        :return: Enterprising investors intrinsic value, aka a company's Serenity Number.
        """
        return self.values.serenity_number


    @property
    def current_assets_gte_150pct_long_term_debt(self) -> pd.Series:
        values = self.values.current_assets_150pct_long_term_debt()
        return _nullable_comparison(
            values,
            lambda series: series >= ENTERPRISING_CURRENT_RATIO_MIN,
            "currentAssetsGte150pctLongTermDebt",
        )


    def long_term_debt_lte_110pct_net_current_assets(self) -> pd.Series:
        """
        Total liabilities should not have a value greater than 110% of the value of the company's net current assets.
        :return: True if 1.1x totalLiabilities <= totalCurrentAssets, else False
        """
        values = self.values.long_term_debt_110pct_net_current_assets()
        return _nullable_comparison(
            values,
            lambda series: series <= ENTERPRISING_MAX_DEBT_TO_NET_CURRENT_ASSETS,
            "longTermDebtLte110pctNetCurrentAssets",
        )


    def some_current_dividend(self) -> pd.Series:
        """
        Simply have continuous dividend payouts over at least 5 years.
        :return: True if year_n divpayout > 0 for each of the previous 5 years, else False
        """
        values = self.values.some_current_dividend()
        return _nullable_comparison(
            values,
            lambda series: series > 0,
            "someDividendPayout",
        )


    def pos_earnings(self) -> pd.Series:
        """
        Company must have positive earnings for at least 5 years.
        :return: True if year_n eps > 0 for each of the previous 5 years, else False
        """
        return _rolling_all_positive(
            self.values.pos_earnings(),
            5,
            "positiveEarnings5yr",
        )


    def earnings_growth_5yr(self) -> pd.Series:
        """
        year n earnings growth greater than 4 years prior to n
        :return: True if eps > 0 for year n and 4 years prior to n, else False
        """
        values = self.values.earnings_growth_5yr()
        return _nullable_comparison(
            values,
            lambda series: series > 0,
            "currentEarningsGreater5YrsPrior",
        )


    def earnings_greater_than_5yr_lookback(self) -> pd.Series:
        values = self.values.earnings_to_5yr_lookback_ratio()
        return _nullable_comparison(
            values,
            lambda series: series > 1,
            "earningsGreaterThan5yrLookback",
        )


    def price_lte_120pct_tangible_assets(self) -> pd.Series:
        """
        price less than or equal to 120% of tangible assets
        :return: True if price <= 120% of tangible assets, else False
        """
        values = self.values.price_120pct_tangible_assets()
        return _nullable_comparison(
            values,
            lambda series: series <= ENTERPRISING_MAX_PRICE_TO_TANGIBLE_BOOK,
            "priceLte120pctTangibleAssets",
        )


    def enterprising_margin_of_safety(self) -> pd.Series:
        """
        The Enterprising Investor's margin of safety is the Serenity Number divided by the current market price.
        A value greater than 1.0 means the stock is undervalued and selling at a discount to the Serenity Number.
        :return: Serenity Number / Market Price for analysis period
        """
        return self.values.enterprising_margin_of_safety()


    def enterprising_investor(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "fiscalDateEnding": self._df.fiscalDateEnding,
                "serenityNumber": self.serenity_number(),
                "enterprisingMarginOfSafety": self.enterprising_margin_of_safety(),
                "closingSharePrice": self.values._series("closingSharePrice"),
            }
        )


    def criteria_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "fiscalDateEnding": self._df.fiscalDateEnding,
                "currentAssetsGte150pctLongTermDebt": self.current_assets_gte_150pct_long_term_debt,
                "longTermDebtLte110pctNetCurrentAssets": self.long_term_debt_lte_110pct_net_current_assets(),
                "positiveEarnings5yr": self.pos_earnings(),
                "earningsGreaterThan5yrLookback": self.earnings_greater_than_5yr_lookback(),
                "priceLte120pctTangibleAssets": self.price_lte_120pct_tangible_assets()
            }
        )


    def criteria_dict(self):
        return {
                "fiscalDateEnding": self._df.fiscalDateEnding,
                "currentAssetsGte150pctLongTermDebt": self.current_assets_gte_150pct_long_term_debt,
                "longTermDebtLte110pctNetCurrentAssets": self.long_term_debt_lte_110pct_net_current_assets(),
                "positiveEarnings5yr": self.pos_earnings(),
                "earningsGreaterThan5yrLookback": self.earnings_greater_than_5yr_lookback(),
                "priceLte120pctTangibleAssets": self.price_lte_120pct_tangible_assets()
            }
