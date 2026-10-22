# Financial metrics used to gauge the quality of a company.

import numpy as np
import datetime as dt
import pandas as pd
import sqlite3
# FinancialAssessment class to be used to derive financial metrics from the financial statements and market price history
class FinancialAssessment:

    def __init__(
            self,
            ticker: str,
            date: str | None = None,
            years: int = 5,
            market_price_date: str | None = None,
    ):
        # import the needed modules
        from data_access.BalanceSheets import BalanceSheets as BS
        from data_access.CashFlow import CashFlow as CF
        from data_access.IncomeStatements import IncomeStatements as IS
        from data_access.EarningsReports import EarningsReports as ER
        from data_access.OHLCVPriceData import OHLCVPriceData as OHLCV
        from data_access.CompanyDetails import CompanyDetails as CD
        from data_access.PipelineETL import (
            FinancialData_by_date,
            has_minimum_annual_history,
        )

        if not isinstance(ticker, str):
            raise TypeError("ticker must be a string")
        ticker = ticker if ticker.isupper() else ticker.upper()

        if years is None or not isinstance(years,int):
            raise TypeError("years must be an integer")
        elif years < 5:
            raise ValueError("years must be greater than or equal to 5")

        if not has_minimum_annual_history(ticker,years=years):
            raise ValueError(
                f"Ticker {ticker} does not have minimum annual history."
            )
        # verify there is a usable date to start with
        if date is None:
            date = dt.datetime.now().strftime('%Y-%m-%d')
        # verify the existence of a usable date to start with
        if date is not None and not isinstance(date, str):
            raise TypeError("date must be a string")
        elif date:
            try:
                dt.datetime.fromisoformat(date)
            except ValueError:
                raise ValueError("date must be a valid ISO 8601 date string")

        if market_price_date is None:
            market_price_date = date
        if not isinstance(market_price_date, str):
            raise TypeError("market_price_date must be a string")
        try:
            market_price_dt = dt.datetime.fromisoformat(market_price_date)
        except ValueError:
            raise ValueError(
                "market_price_date must be a valid ISO 8601 date string"
            )


        object.__setattr__(self, '_ticker', ticker)
        object.__setattr__(self, '_bs', BS(ticker))
        object.__setattr__(self, '_cf', CF(ticker))
        object.__setattr__(self, '_is', IS(ticker))
        object.__setattr__(self, '_er', ER(ticker))
        object.__setattr__(self, '_ohlcv', OHLCV(ticker))
        object.__setattr__(self, '_cd', CD(ticker))


        er_date = self._as_date_string(self._er.get_closest_date(date=date))
        bs_date = self._as_date_string(self._bs.get_closest_date(date=date))
        cf_date = self._as_date_string(self._cf.get_closest_date(date=date))
        inc_date = self._as_date_string(self._is.get_closest_date(date=date))

        object.__setattr__(self, '_er_date', er_date)
        object.__setattr__(self, '_bs_date', bs_date)
        object.__setattr__(self, '_cf_date', cf_date)
        object.__setattr__(self, '_is_date', inc_date)

       # set financial date for the financial statements.
        _annual_fin_date = min(dt.datetime.fromisoformat(fd) for fd in (er_date, bs_date, cf_date, inc_date))
        _annual_fin_date = self._as_date_string(_annual_fin_date)
        dt_date = dt.datetime.fromisoformat(date)
        share_price_analysis_date = self._ohlcv.get_closest_date(
            date=market_price_dt
        )
        share_price_analysis_date = self._as_date_string(share_price_analysis_date)
        quarter = quarter_analysis_date(self._ticker,dt_date)


        object.__setattr__(self, '_quarter_analysis_date', quarter)
        object.__setattr__(self, '_annual_fin_analysis_date', _annual_fin_date)
        object.__setattr__(self, '_share_price_analysis_date', share_price_analysis_date)
        object.__setattr__(self, '_market_price_date', market_price_date)
        object.__setattr__(self, '_date', date)

        object.__setattr__(
            self,
            '_ttm',
            FinancialData_by_date._trailing_twelve_months(
                self._is.quarterly(),
                self._er.quarterly(),
                self._date,
            ),
        )
    @staticmethod
    def _as_date_string(value):
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')
        return str(value)

    @staticmethod
    def _as_number(value, default=0.0):
        if value is None:
            return default
        if isinstance(value, (int, float, np.integer, np.floating)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _optional_number(value):
        """Return a finite number without manufacturing a value for missing data."""
        if value is None or value is pd.NA:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if np.isfinite(number) else None

    @classmethod
    def _first_number(cls, values, *keys):
        for key in keys:
            number = cls._optional_number(values.get(key))
            if number is not None:
                return number
        return None

    @staticmethod
    def _as_dict(value):
        return value if isinstance(value, dict) else {}

    def _balance_sheet(self):
        return self._as_dict(self._bs.get_by_date(self._annual_fin_analysis_date))

    def _cash_flow(self):
        return self._as_dict(self._cf.get_by_date(self._annual_fin_analysis_date))

    def _income_statement(self):
        return self._as_dict(self._is.get_by_date(self._annual_fin_analysis_date))

    def _earnings_report(self):
        return self._as_dict(self._er.get_by_date(self._annual_fin_analysis_date))

    def _price(self):
        return self._as_dict(self._ohlcv.price_on_date(self._share_price_analysis_date))

    def _previous_annual_balance_sheet(self):
        annual = self._bs.annual()
        if not isinstance(annual, pd.DataFrame) or annual.empty:
            return {}
        if 'fiscalDateEnding' not in annual.columns:
            return {}

        current_date = pd.to_datetime(
            self._annual_fin_analysis_date,
            errors='coerce',
        )
        if pd.isna(current_date):
            return {}

        dated = annual.copy()
        dated['_fiscal_date'] = pd.to_datetime(
            dated['fiscalDateEnding'],
            errors='coerce',
        )
        prior = dated[
            dated['_fiscal_date'].notna()
            & (dated['_fiscal_date'] < current_date)
        ].sort_values('_fiscal_date', ascending=False)
        if prior.empty:
            return {}
        return prior.iloc[0].drop(labels=['_fiscal_date']).to_dict()

    def _total_debt(self, balance_sheet):
        total_debt = self._first_number(
            balance_sheet,
            'shortLongTermDebtTotal',
        )
        if total_debt is not None:
            return total_debt

        current_debt = self._first_number(
            balance_sheet,
            'currentDebt',
            'shortTermDebt',
        )
        long_term_debt = self._first_number(
            balance_sheet,
            'longTermDebtNoncurrent',
            'longTermDebt',
        )
        if current_debt is None or long_term_debt is None:
            return None
        return current_debt + long_term_debt

    def _cash_and_short_term_investments(self, balance_sheet):
        return self._first_number(
            balance_sheet,
            'cashAndShortTermInvestments',
            'cashAndCashEquivalentsAtCarryingValue',
        )

    def _shareholders_equity(self, balance_sheet):
        equity = self._first_number(
            balance_sheet,
            'totalShareholderEquity',
            'totalShareholdersEquity',
        )
        if equity is not None:
            return equity

        assets = self._optional_number(balance_sheet.get('totalAssets'))
        liabilities = self._optional_number(
            balance_sheet.get('totalLiabilities')
        )
        if assets is None or liabilities is None:
            return None
        return assets - liabilities

    def _invested_capital(self, balance_sheet):
        equity = self._shareholders_equity(balance_sheet)
        debt = self._total_debt(balance_sheet)
        cash = self._cash_and_short_term_investments(balance_sheet)
        if equity is None or debt is None or cash is None:
            return None
        return equity + debt - cash

    def _capital_employed(self, balance_sheet):
        assets = self._optional_number(balance_sheet.get('totalAssets'))
        current_liabilities = self._optional_number(
            balance_sheet.get('totalCurrentLiabilities')
        )
        if assets is None or current_liabilities is None:
            return None
        return assets - current_liabilities

    def _magic_formula_balance_sheet(self):
        annual = self._balance_sheet()
        try:
            quarterly = self._as_dict(
                self._bs.get_by_date(self._date, quarterly=True)
            )
        except ValueError:
            quarterly = {}

        # Alpha Vantage frequently omits fields such as PPE from quarterly
        # balance sheets. Overlay only populated quarterly values so the latest
        # annual value remains available instead of being treated as zero.
        result = dict(annual)
        for key, value in quarterly.items():
            if value is None:
                continue
            if isinstance(value, (float, np.floating)) and np.isnan(value):
                continue
            result[key] = value
        return result

    def eps_ttm(self):
        return self._as_number(self._ttm.get('epsTTM'), default=np.nan)

    def net_income_ttm(self):
        return self._as_number(self._ttm.get('earningsTTM'), default=np.nan)

    def ebit_ttm(self):
        return self._as_number(self._ttm.get('ebitTTM'), default=np.nan)


    def gross_margin(self):
        # gross profit compared to total revenue
        inc = self._income_statement()
        if inc and isinstance(inc,dict):
            tot_rev = self._as_number(inc.get('totalRevenue',0.0))
            cogs = self._as_number(inc.get('costofGoodsAndServicesSold',0.0))
            # don't reverse the universe...
            if tot_rev == 0:
                return np.nan
            gm = (tot_rev - cogs) / tot_rev
            return gm
        else:
            return np.nan


    def free_cash_flow(self):
        # Cash generated after the capital expenditures needed by the business.
        cf = self._cash_flow()
        if not isinstance(cf, dict):
            return None
        ocf = self._optional_number(cf.get('operatingCashflow'))
        capex = self._optional_number(cf.get('capitalExpenditures'))
        if ocf is None or capex is None:
            return None
        return ocf - capex


    def free_cash_flow_margin(self):
        # Latest completed annual free cash flow divided by annual revenue.
        fcf = self.free_cash_flow()
        revenue = self._optional_number(
            self._income_statement().get('totalRevenue')
        )
        if fcf is None or revenue is None or revenue <= 0:
            return None
        return fcf / revenue

    def estimated_owner_earnings(self):
        """Return the documented owner-earnings proxy: OCF less capex."""
        return self.free_cash_flow()

    def estimated_owner_earnings_yield(self):
        """Return annual estimated owner earnings divided by market cap."""
        owner_earnings = self.estimated_owner_earnings()
        balance_sheet = self._balance_sheet()
        shares = self._first_number(
            balance_sheet,
            'commonStockSharesOutstanding',
            'commonStockOutstanding',
        )
        price = self._optional_number(self._price().get('close'))
        if owner_earnings is None or shares is None or price is None:
            return None
        market_cap = shares * price
        if market_cap <= 0:
            return None
        return owner_earnings / market_cap


    def operating_income(self):
        inc = self._income_statement()
        if inc and isinstance(inc,dict):
            revenue = self._as_number(inc.get('totalRevenue',0.0))
            cost = self._as_number(inc.get('costofGoodsAndServicesSold',0.0 ))
            opex = self._as_number(inc.get('operatingExpenses',0.0))
            op_inc = revenue - cost - opex
            return op_inc
        else:
            return np.nan


    def inventory_turnover(self):
        # inventory divided by total revenue; describes the number of times inventory is sold and replaced
        inv = self._balance_sheet()
        revenue = self._income_statement()

        if inv and revenue and isinstance(revenue,dict):
            revenue = self._as_number(revenue.get('totalRevenue',0.0))
            inventory = self._as_number(inv.get('inventory', 0.0))
            # dont reverse the universe...
            if not inventory:
                return np.nan
            inv_turnover = revenue / inventory
            return inv_turnover
        else:
            return np.nan


    def return_on_equity(self):
        # net income divided by shareholder's equity: if not available, use total assets minus total liabilities
        bs = self._balance_sheet()
        inc = self._income_statement()
        if all((bs,inc,isinstance(bs,dict),isinstance(inc,dict))):
            total_shareholders_equity = bs.get('totalShareholdersEquity')
            if not total_shareholders_equity:
                tot_assets = self._as_number(bs.get('totalAssets',0.0))
                tot_liabilities = self._as_number(bs.get('totalLiabilities',0.0))

                total_shareholders_equity = tot_assets - tot_liabilities

            equity = self._as_number(total_shareholders_equity)

            # don't reverse the universe...
            if not equity or equity == 0:
                return np.nan

            net_income = self._as_number(inc.get('netIncome',0.0))
            if not net_income:
                return np.nan

            roe = net_income / equity

            return roe
        else:
            return np.nan


    def return_on_assets(self):
        # net income divided by total assets to measure the company's assets vs. what was earned
        bs = self._balance_sheet()
        inc = self._income_statement()
        if all((bs, inc, isinstance(bs, dict), isinstance(inc, dict))):
            net_income = self._as_number(inc.get('netIncome', 0.0))
            tot_assets = self._as_number(bs.get('totalAssets',0.0))
            # don't reverse the universe...
            if tot_assets == 0:
                return np.nan
            roa = net_income / tot_assets
            return roa
        else:
            return np.nan


    def return_on_invested_capital(self):
        # Annual NOPAT divided by average annual invested capital.
        bs = self._balance_sheet()
        prior_bs = self._previous_annual_balance_sheet()
        inc = self._income_statement()
        if not bs or not prior_bs or not inc:
            return None

        ebit = self._optional_number(inc.get('ebit'))
        income_before_tax = self._optional_number(inc.get('incomeBeforeTax'))
        income_tax = self._optional_number(inc.get('incomeTaxExpense'))
        current_capital = self._invested_capital(bs)
        prior_capital = self._invested_capital(prior_bs)
        if any(
            value is None
            for value in (
                ebit,
                income_before_tax,
                income_tax,
                current_capital,
                prior_capital,
            )
        ):
            return None
        if income_before_tax <= 0 or income_tax < 0:
            return None

        effective_tax_rate = income_tax / income_before_tax
        if not 0 <= effective_tax_rate <= 1:
            return None
        average_invested_capital = (current_capital + prior_capital) / 2
        if average_invested_capital <= 0:
            return None

        nopat = ebit * (1 - effective_tax_rate)
        return nopat / average_invested_capital

    def financial_profile_return_on_capital(self):
        """Return annual EBIT divided by average annual capital employed."""
        bs = self._balance_sheet()
        prior_bs = self._previous_annual_balance_sheet()
        inc = self._income_statement()
        if not bs or not prior_bs or not inc:
            return None

        ebit = self._optional_number(inc.get('ebit'))
        current_capital = self._capital_employed(bs)
        prior_capital = self._capital_employed(prior_bs)
        if ebit is None or current_capital is None or prior_capital is None:
            return None
        average_capital = (current_capital + prior_capital) / 2
        if average_capital <= 0:
            return None
        return ebit / average_capital

    def eps_cagr_5yr(self):
        """Return EPS CAGR from five aligned annual observations."""
        earnings = self._er.annual()
        income = self._is.annual()
        required_earnings_columns = {'fiscalDateEnding', 'reportedEPS'}
        if (
            not isinstance(earnings, pd.DataFrame)
            or not isinstance(income, pd.DataFrame)
            or earnings.empty
            or income.empty
            or not required_earnings_columns.issubset(earnings.columns)
            or 'fiscalDateEnding' not in income.columns
        ):
            return None

        current_date = pd.to_datetime(
            self._annual_fin_analysis_date,
            errors='coerce',
        )
        if pd.isna(current_date):
            return None

        annual_dates = pd.DataFrame(
            {
                '_fiscal_date': pd.to_datetime(
                    income['fiscalDateEnding'],
                    errors='coerce',
                )
            }
        ).dropna().drop_duplicates()
        eps_history = earnings[['fiscalDateEnding', 'reportedEPS']].copy()
        eps_history['_fiscal_date'] = pd.to_datetime(
            eps_history['fiscalDateEnding'],
            errors='coerce',
        )
        eps_history = eps_history.merge(annual_dates, on='_fiscal_date')
        eps_history = eps_history[
            eps_history['_fiscal_date'].notna()
            & (eps_history['_fiscal_date'] <= current_date)
        ].copy()
        if eps_history.empty:
            return None

        eps_history['_fiscal_year'] = eps_history['_fiscal_date'].dt.year
        eps_history = eps_history.sort_values(
            '_fiscal_date',
            ascending=False,
        ).drop_duplicates('_fiscal_year')
        required_years = list(range(current_date.year - 4, current_date.year + 1))
        by_year = eps_history.set_index('_fiscal_year')
        if any(year not in by_year.index for year in required_years):
            return None

        first_eps = self._optional_number(
            by_year.loc[required_years[0], 'reportedEPS']
        )
        last_eps = self._optional_number(
            by_year.loc[required_years[-1], 'reportedEPS']
        )
        if first_eps is None or last_eps is None:
            return None
        if first_eps <= 0 or last_eps <= 0:
            return None
        growth_intervals = len(required_years) - 1
        return (last_eps / first_eps) ** (1 / growth_intervals) - 1


    def return_on_capital(self):
        # Magic Formula numerator uses trailing-twelve-month EBIT.
        bs = self._magic_formula_balance_sheet()
        ebit = self.ebit_ttm()
        if bs and ebit:
            curr_assets = self._as_number(bs.get('totalCurrentAssets'))
            curr_liab = self._as_number(bs.get('totalCurrentLiabilities'))
            cash_and_equiv = self._as_number(bs.get('cashAndCashEquivalentsAtCarryingValue'))
            ppe = self._as_number(
                bs.get(
                    'propertyPlantEquipment',
                    bs.get('propertyPlantEquipmentNet'),
                )
            )
            depr_amort = self._as_number(
                bs.get(
                    'accumulatedDepreciationAmortizationPPE',
                    bs.get('accumulatedDepreciationAndAmortization'),
                )
            )

            denominator = curr_assets - cash_and_equiv + ppe + depr_amort - curr_liab
            if not denominator:
                return np.nan

            roc = ebit / denominator

            return roc
        else:
            return np.nan


    def earnings_yield(self):
        # Magic Formula numerator uses trailing-twelve-month EBIT.
        price = self._as_number(self._price().get('close', 0.0))
        ebit = self.ebit_ttm()
        if np.isnan(ebit):
            return np.nan
        bs = self._magic_formula_balance_sheet()
        if not bs:
            return np.nan
        comm_stk_outstd = self._as_number(
            bs.get(
                'commonStockSharesOutstanding',
                bs.get('commonStockOutstanding', 0.0),
            )
        )
        shortlongdebt = self._as_number(bs.get('shortLongTermDebtTotal'), 0.0)

        market_cap = comm_stk_outstd * price
        denominator = market_cap + shortlongdebt
        if not denominator:
            return np.nan

        ey = ebit / denominator
        ey = ey if ey != 0 else np.nan

        return ey


    def magic_formula_score(self):
        roc = self.return_on_capital()
        ey = self.earnings_yield()
        if np.isnan(roc) or np.isnan(ey):
            return np.nan
        return roc + ey


    def magic_formula_values(self) -> dict:
        """Return only the point-in-time values needed to build rankings."""
        return {
            "ticker": self._ticker,
            "quarter_date": self._as_date_string(self._date),
            "associated_annual_date": self._as_date_string(
                self._annual_fin_analysis_date
            ),
            "return_on_capital": self.return_on_capital(),
            "earnings_yield": self.earnings_yield(),
        }


    def magic_formula_ranking(self, conn=None) -> dict:
        """Return this ticker's latest persisted rank on or before analysis."""
        owns_connection = conn is None
        if conn is None:
            from Securities_DB.db_connection import get_connection

            try:
                conn = get_connection(analysis="magic_formula", readonly=True)
            except sqlite3.Error:
                return {}

        try:
            row = conn.execute(
                """
                SELECT ticker,
                       quarter_date,
                       associated_annual_date,
                       financial_statement_availability_date,
                       magic_formula_rank,
                       return_on_capital_rank,
                       earnings_yield_rank,
                       total_roc_ey_score
                FROM magic_formula_quarterly_results
                WHERE ticker = ?
                  AND quarter_date <= ?
                ORDER BY quarter_date DESC
                LIMIT 1
                """,
                (self._ticker, self._as_date_string(self._date)),
            ).fetchone()
        except sqlite3.Error:
            return {}
        finally:
            if owns_connection:
                conn.close()

        return dict(row) if row is not None else {}



    def debt_to_equity(self):
        # debt divided by a company's total equity
        bs = self._balance_sheet()
        if bs and isinstance(bs,dict):
            tot_assets = self._as_number(bs.get('totalAssets',0.0))
            tot_liabilities = bs.get('totalLiabilities',0.0)

            if not tot_liabilities:
                return np.nan

            equity = tot_assets - tot_liabilities
            # don't reverse the universe...
            if not equity:
                return np.nan

            debt_to_equity = tot_liabilities / equity

            return debt_to_equity
        else:
            return np.nan


    def debt_to_assets(self):
        # Interest-bearing debt divided by latest completed annual assets.
        bs = self._balance_sheet()
        if not isinstance(bs, dict):
            return None
        total_assets = self._optional_number(bs.get('totalAssets'))
        total_debt = self._total_debt(bs)
        if total_assets is None or total_debt is None or total_assets <= 0:
            return None
        return total_debt / total_assets


    def interest_coverage(self):
        # ebit divided by interest_expenses to measure how well a company can pay interest due on debt
        inc = self._income_statement()
        if inc and isinstance(inc,dict):
            ebit = self._as_number(inc.get('ebit',0.0))
            interest_expenses = self._as_number(inc.get('interestExpense',0.0))
            # don't reverse the universe...
            if not interest_expenses:
                return np.nan
            return ebit / interest_expenses
        else:
            return np.nan


    def net_debt_to_free_cash_flow(self):
        # Net debt divided by positive annual FCF; negative net debt is valid.
        bs = self._balance_sheet()
        fcf = self.free_cash_flow()
        if not isinstance(bs, dict) or fcf is None or fcf <= 0:
            return None
        total_debt = self._total_debt(bs)
        cash = self._cash_and_short_term_investments(bs)
        if total_debt is None or cash is None:
            return None
        return (total_debt - cash) / fcf


    def longterm_debt_to_cash(self) -> float:
        # can longterm debt be covered by the available cash?
        cf = self._cash_flow()
        bs = self._balance_sheet()
        if not isinstance(cf, dict) or not isinstance(bs, dict):
            return np.nan

        cash_bal = cf | bs
        if not cash_bal:
            return np.nan

        ltd = cash_bal.get('longTermDebt', np.nan)
        if not ltd:
            return 0.0

        cash = self._as_number(
            cash_bal.get('cashAndCashEquivalentsAtCarryingValue', np.nan)
        )
        operating_cashflow = self._as_number(cash_bal.get('operatingCashflow', np.nan))
        capital_expenditures = self._as_number(
            cash_bal.get('capitalExpenditures', np.nan)
        )
        all_cash_and_equivalents = cash + operating_cashflow - capital_expenditures

        if not all_cash_and_equivalents:
            return np.nan

        return ltd / all_cash_and_equivalents


    def total_sales_services(self):
        # total amount of revenue a company accumulated over the fiscal period
        return self._as_number(self._income_statement().get('totalRevenue',0.0))

    def to_dict(self):
        # return a dictionary of all the metrics
        company_details = self._cd.get_details()
        company_name = company_details.get('Name', '')
        company_description = company_details.get('Description') or None
        sector = company_details.get('Sector', '')
        industry = company_details.get('Industry', '')
        eps = self._as_number(self._earnings_report().get('reportedEPS', 0.0))

        price_data = self._price()
        share_price = self._as_number(price_data.get('close', 0.0))
        raw_price_date = price_data.get('date') or self._share_price_analysis_date
        selected_price_date = self._as_date_string(raw_price_date)
        price_window = min_max_mean_200_day_price(
            self._ticker,
            selected_price_date,
        )
        min_200_day_price = self._as_number(price_window.get('min', 0.0))
        max_200_day_price = self._as_number(price_window.get('max', 0.0))
        avg_price_200_day = self._as_number(price_window.get('mean', 0.0))
        median_price_200_day = self._as_number(price_window.get('median', 0.0))

        eps_ttm = self._as_number(self.eps_ttm())
        price_to_earnings = share_price / eps_ttm if eps_ttm else None
        bs = self._balance_sheet()
        comm_shares_outstd = self._as_number(bs.get('commonStockSharesOutstanding', 0.0))
        capitalization = share_price * comm_shares_outstd

        if capitalization >= 2e11:
            cap_group = 'Mega'
        elif capitalization >= 1e10:
            cap_group = 'Large'
        elif capitalization >= 2e9:
            cap_group = 'Mid'
        elif capitalization >= 25e7:
            cap_group = 'Small'
        elif capitalization >= 1e8:
            cap_group = 'Micro'
        else:
            cap_group = 'Nano'

        ranking = self.magic_formula_ranking()

        return {
            'ticker': self._ticker,
            'company_name': company_name,
            'company_description': company_description,
            'analysis_date': self._as_date_string(self._date), # actual date of analysis
            'price_date': selected_price_date, # actual market trading date used for price selection
            'annual_financial_statement_analysis_date': self._as_date_string(self._annual_fin_analysis_date),
            'quarter_financial_statement_analysis_date':self._as_date_string(self._quarter_analysis_date),
            'market_price_for_period': share_price,
            'min_200_day_price': min_200_day_price,
            'max_200_day_price': max_200_day_price,
            'avg_price_200_day': avg_price_200_day,
            'median_price_200_day': median_price_200_day,
            'market_cap': capitalization,
            'market_cap_group': cap_group,
            'sector':sector,
            'industry':industry,
            'eps': eps,
            'eps_ttm': eps_ttm,
            'net_income_ttm': self.net_income_ttm(),
            'ebit_ttm': self.ebit_ttm(),
            'price_to_earnings': price_to_earnings,
            'gross_margin': self.gross_margin(),
            'free_cash_flow': self.free_cash_flow(),
            'free_cash_flow_margin': self.free_cash_flow_margin(),
            'estimated_owner_earnings': self.estimated_owner_earnings(),
            'estimated_owner_earnings_yield': self.estimated_owner_earnings_yield(),
            'operating_income': self.operating_income(),
            'inventory_turnover': self.inventory_turnover(),
            'financial_profile_return_on_capital': self.financial_profile_return_on_capital(),
            'return_on_capital': self.return_on_capital(),
            'earnings_yield': self.earnings_yield(),
            'magic_formula_quarter_date': ranking.get('quarter_date'),
            'magic_formula_associated_annual_date': ranking.get(
                'associated_annual_date'
            ),
            'magic_formula_financial_statement_availability_date': ranking.get(
                'financial_statement_availability_date'
            ),
            'magic_formula_rank': ranking.get('magic_formula_rank'),
            'return_on_capital_rank': ranking.get('return_on_capital_rank'),
            'earnings_yield_rank': ranking.get('earnings_yield_rank'),
            'total_roc_ey_score': ranking.get('total_roc_ey_score'),
            'return_on_assets': self.return_on_assets(),
            'return_on_equity': self.return_on_equity(),
            'return_on_invested_capital': self.return_on_invested_capital(),
            'eps_cagr_5yr': self.eps_cagr_5yr(),
            'debt_to_assets': self.debt_to_assets(),
            'debt_to_equity': self.debt_to_equity(),
            'net_debt_to_free_cash_flow': self.net_debt_to_free_cash_flow(),
            'longterm_debt_to_cash': self.longterm_debt_to_cash(),
            'interest_coverage': self.interest_coverage(),
            'total_sales_services': self.total_sales_services(),
        }


# Business quarter mapper
def quarter_selector(year:int)->dict:
    Q1 = dt.datetime(year,1,1),dt.datetime(year,3,31)
    Q2 = dt.datetime(year,4,1),dt.datetime(year,6,30)
    Q3 = dt.datetime(year,7,1),dt.datetime(year,9,30)
    Q4 = dt.datetime(year,10,1),dt.datetime(year,12,31)
    return {
        'Q1':Q1,
        'Q2':Q2,
        'Q3':Q3,
        'Q4':Q4,
    }


# Date to quarter mapping
def quarter_group_mapper(date: str | dt.datetime)->str:
    if isinstance(date,str):
        try:
            date = dt.datetime.fromisoformat(date)
        except ValueError:
            raise ValueError("if 'date' argument is a string object; it must be in ISO format YYYY-MM-DD")
    elif not isinstance(date,dt.datetime):
        raise ValueError("'date' argument must be datetime.datetime class object.")

    year = date.year
    quarter = quarter_selector(year)
    for key in quarter.keys():
        if quarter[key][0] <= date <= quarter[key][1]:
            return key

    return ''


def quarter_analysis_date(ticker:str,date:str|dt.datetime|None = None)->str | None:
    from data_access.EarningsReports import EarningsReports as ER
    if not isinstance(ticker, str):
        raise ValueError("'ticker' argument must be a string object.")
    ticker = ticker if ticker.isupper() else ticker.upper()

    # uses a price approximately one week following the financial reporting date
    if date:
        if isinstance(date,str):
            try:
                dt_date = dt.datetime.fromisoformat(date)
            except ValueError:
                raise ValueError("if 'date' argument is a string object; it must be in ISO format YYYY-MM-DD")
        elif not isinstance(date,dt.datetime):
            raise ValueError("'date' argument must be datetime.datetime class object.")
        elif hasattr(date,'strftime'):
            dt_date = date

        else:
            raise ValueError("'date' argument must be datetime.datetime class object or string object: 'YYYY-MM-DD'.")

    elif date is None:
        date = ER(ticker).quarterly().fiscalDateEnding.iloc[0]
        try:
            dt_date = dt.datetime.fromisoformat(date)
        except ValueError:
            raise ValueError("if 'date' argument is a string object; it must be in ISO format YYYY-MM-DD")

    try:
        hasattr(dt_date,'year')
    except AttributeError:
        raise ValueError("'date' argument must be datetime.datetime class object.")

    quarter = quarter_group_mapper(dt_date)
    quarter_analysis_date = {
        'Q1': dt.datetime(dt_date.year - 1, 12, 31),
        'Q2': dt.datetime(dt_date.year, 3, 31),
        'Q3': dt.datetime(dt_date.year, 6, 30),
        'Q4': dt.datetime(dt_date.year, 9, 30),
    }
    q_a_d = quarter_analysis_date.get(quarter)
    return q_a_d.strftime('%Y-%m-%d') if q_a_d else None


def annual_quarter_grouping(ticker:str,date:None | str = None)->dict:
    from data_access.EarningsReports import EarningsReports as ER
    from data_access.CompanyDetails import CompanyDetails as CD

    ticker = ticker if ticker.isupper() else ticker.upper()

    er = ER(ticker)
    cd = CD(ticker).get_details()
    if not isinstance(cd,dict) or 'FiscalYearEnd' not in cd:
        return {}
    fiscal_month = cd.get('FiscalYearEnd')

    annual_quarter_groupings = {}

    if date:
        if not isinstance(date, str):
            raise ValueError("date must be a string in format YYYY-MM-DD")
        annual_dates = er.annual().get('fiscalDateEnding').tolist()
        quarter_dates = er.quarterly()['fiscalDateEnding']
        if date not in annual_dates:
            date = er.get_closest_date(date,quarterly=False)
        a_idx = annual_dates.index(date)
        annual_dates = annual_dates[a_idx:]

        for _d in annual_dates:
            _dt = dt.datetime.fromisoformat(_d)
            if _dt.strftime("%B") == fiscal_month:
                year = _d.split('-')[0]
                if not year.isnumeric():
                    continue
                else:
                    quarter_idx = quarter_dates[quarter_dates == _d].index[0]
                    quart_group = quarter_dates.iloc[quarter_idx:quarter_idx + 4].tolist()
                    annual_quarter_groupings[year] = quart_group

        return annual_quarter_groupings

    # start with the years
    else:
        annual_dates = er.annual().get('fiscalDateEnding').tolist()
        quarter_dates = er.quarterly()['fiscalDateEnding']

        for _d in annual_dates:
            _dt = dt.datetime.fromisoformat(_d)
            if _dt.strftime("%B") == fiscal_month:
                year = _d.split('-')[0]
                if not year.isnumeric():
                    continue
                else:
                    quarter_idx = quarter_dates[quarter_dates == _d].index[0]
                    quart_group = quarter_dates.iloc[quarter_idx:quarter_idx + 4].tolist()
                    annual_quarter_groupings[year] = quart_group

    return annual_quarter_groupings


def min_max_mean_200_day_price(ticker:str,date:str|None)->dict:
    from data_access.OHLCVPriceData import OHLCVPriceData as OHLCV

    # returns a dictionary of a min,max,mean of the closing prices of a ticker from a pandas dataframe

    if not isinstance(ticker,str):
        raise ValueError("ticker must be a string")
    try:
        ticker = ticker if ticker.isupper() else ticker.upper()
    except ValueError:
        raise ValueError("ticker must be a string")

    ohlcv = OHLCV(ticker)

    if date:
        if not isinstance(date,str):
            raise ValueError("date must be a string in format YYYY-MM-DD")
        if isinstance(date,str):
            try:
                dt.datetime.fromisoformat(date)
            except ValueError:
                raise ValueError("date must be a string in format YYYY-MM-DD")
        date = ohlcv.get_closest_date(date)

    df = ohlcv.closing_prices()
    if df.empty:
        return {
            'min':None,
            'max':None,
            'mean':None,
            'median':None,
            'min_date':None,
            'max_date':None
        }

    first = df.index[0].strftime('%Y-%m-%d')
    last = df.index[-1].strftime('%Y-%m-%d')

    if pd.to_datetime(first) < pd.to_datetime(last):
        df = df.iloc[-1::-1]

    if date:
        df = df.loc[date:]
    df = df.iloc[:200].copy()

    return {
        'min':df.close.min(),
        'max':df.close.max(),
        'mean':df.close.mean(),
        'median':df.close.median(),
        'min_date': df[df.close == df.close.min()].index[0].strftime('%Y-%m-%d'),
        'max_date': df[df.close == df.close.max()].index[0].strftime('%Y-%m-%d')
    }
