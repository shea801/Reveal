# -- Python 3.14 UTF-8 encoding --


import os
import json
import math
import datetime as dt
from data_access.file_parsing import load_json_from_file_safe
from data_access.CompanyDetails import CompanyDetails as CD
from data_ingestion.alphavantage_api import make_alphavantage_api_call


_SEARCH_RESULT_KEY_MAP = {
    "1. symbol": "symbol",
    "2. name": "name",
    "3. type": "type",
    "4. region": "region",
    "5. marketOpen": "marketOpen",
    "6. marketClose": "marketClose",
    "7. timezone": "timezone",
    "8. currency": "currency",
    "9. matchScore": "matchScore",
}

_COMPANY_OVERVIEW_KEYS = (
    "Symbol",
    "Name",
    "Exchange",
    "AssetType",
    "Currency",
    "Country",
    "FiscalYearEnd",
)


class CompanyOverviewResult:
    def __init__(self, data: dict | None):
        self.data = data or {}

    def company_details(self) -> dict:
        return {
            key: self.data.get(key)
            for key in _COMPANY_OVERVIEW_KEYS
            if key in self.data
        }


class DataExtraction:
    def __init__(self,ticker:str=None):
        from data_ingestion.TickerFileSearch import TickerSearch as TS
        super().__init__()
        if ticker and not isinstance(ticker, str):
            raise TypeError("Ticker keyword must be a string or None.")
        if ticker is not None and not isinstance(ticker, str):
            raise TypeError("Ticker keyword must be a string or None.")
        if ticker is not None:
            if not ticker.isupper():
                ticker = ticker.upper()

        object.__setattr__(self, 'ticker', ticker)
        object.__setattr__(self, 'ts', TS())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    def search_ticker(self, ticker: str = None):
        """
        Return normalized Alpha Vantage symbol-search details for a ticker.
        """
        if ticker is not None:
            if not isinstance(ticker, str):
                raise TypeError("Ticker keyword must be a string or None.")
            ticker = ticker.upper()

        data_extraction = DataExtraction(ticker or self.ticker)
        match = data_extraction.search_ticker_alphavantage_api_call()
        if not match:
            return None

        return {
            public_key: match.get(alpha_vantage_key)
            for alpha_vantage_key, public_key in _SEARCH_RESULT_KEY_MAP.items()
            if alpha_vantage_key in match
        }


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    def search_ticker_alphavantage_api_call(self):
        """
        Use this function to grab specific 'ticker search' data from AlphaVantage. Use this as an functional object
        in other functions to simplify the script.
        """

        # AlphaVantage API call is needed ...
        search_data = make_alphavantage_api_call(self.ticker,'symbol_search')

        # verify the information obtained is what you need ...
        if search_data is None:
            print(f"There is no data retrieved from API call for {self.ticker}.")
            return None

        elif not isinstance(search_data, dict):
            print(f"There is no data retrieved from API call for {self.ticker}.")
            return None

        elif 'bestMatches' not in search_data.keys() or not len(search_data['bestMatches']) > 0:
            print(f"There is no best match for {self.ticker} with AlphaVantage.")
            return None

        elif 'bestMatches' in search_data.keys() and len(search_data['bestMatches']) > 0:
            # per AlphaVantage documentation, the data is returned as a dictionary w/ 'bestMatches' as the key
            # it's value is a list of dictionaries: '1. symbol', '2. name', '3. type, and '9. matchScore'
            match = search_data['bestMatches'][0]
            if isinstance(match, dict):
                best = match["9. matchScore"]
                # set the score either 0 or 1 ...
                best = math.floor(float(best))
                if not best:
                    print(f"{self.ticker} had no match in symbol search results.")
                    return None
                else:
                    return match

        else:
            print(f"There is no data retrieved from API call for {self.ticker}.")
            return None


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    def company_details(self, ticker: str = None) -> CompanyOverviewResult:
        """
        Return current Alpha Vantage company-overview details for a ticker.
        """
        if ticker is not None:
            if not isinstance(ticker, str):
                raise TypeError("Ticker keyword must be a string or None.")
            ticker = ticker.upper()

        data_extraction = DataExtraction(ticker or self.ticker)
        return CompanyOverviewResult(data_extraction.company_details_api_call())


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    def company_details_api_call(self):
        """
        Downloads and stores the current company overview (company info, certain TTM and current
        financials, etc.) as a dictionary from JSON file retrieved from AlphaVantage.
        Important keys: Sector,Industry, FiscalYearEnd, LatestQuarter, EPS ,DividendDate, ExDividendDate
        The financials are not official annual US-GAAP numbers (same as quarterly data)!
        """
        data = make_alphavantage_api_call(self.ticker,'company_details')

        if data is None:
            return None

        return data


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



    def price_history_api_call_to_file(self):
        # without a premium account, you can only access AlphaVantage a few times a minute.
        # with the cheapest premium account, you can access AlphaVantage up to 75x's a second

        # AlphaVantage API call
        json_data = make_alphavantage_api_call(self.ticker,'ohlcv')
        if not json_data:
            print(f"{self.ticker} had no price history data.")
            return None
        # Daily adjusted data includes raw OHLCV plus split/dividend fields.
        if 'Meta Data' not in json_data or 'Time Series (Daily)' not in json_data:
            print(f"{self.ticker} does not have meta data or time series data.")
            return None

        daily_data = json_data.get('Time Series (Daily)')
        if not isinstance(daily_data, dict) or not daily_data:
            print(f"{self.ticker} does not have daily adjusted price data.")
            return None
        sample = next(iter(daily_data.values()), {})
        adjusted_keys = {
            '5. adjusted close',
            '6. volume',
            '7. dividend amount',
            '8. split coefficient',
        }
        if not isinstance(sample, dict) or not adjusted_keys.issubset(sample):
            print(f"{self.ticker} response is missing daily adjusted fields.")
            return None

        # set the OHLCV directory
        try:
            paths = self.ts.ticker_file_pathways(self.ticker)
            paths = paths.get('ohlcv')
        except AttributeError as ae:
            print(f"{self.ticker} unable to create filepathway for 'OHLCV. {ae}")
            return None

        if not paths or not isinstance(paths, dict):
            return None

        ohlcv = paths.get('price_hx','')
        meta = paths.get('meta_data','')
        ohlcv_dir = os.path.dirname(ohlcv)

        if not ohlcv or not meta or not isinstance(meta, str) or not isinstance(ohlcv, str):
            return None
        if not ohlcv_dir or not isinstance(ohlcv_dir, str):
            return None

        if not os.path.isdir(ohlcv_dir):
            os.makedirs(ohlcv_dir, exist_ok=True)
        # OHLCV file
        with open(ohlcv, 'w') as jsonfile:
            json.dump(daily_data, jsonfile)
        # Meta data which comes with OHLCV download
        with open(meta, 'w') as jsonfile:
            json.dump(json_data.get('Meta Data'), jsonfile)

        if os.path.isfile(ohlcv) and os.stat(ohlcv).st_size > 0:
            print(f'OHLCV data for {self.ticker} saved to file')
            return None
        else:
            print(f"{self.ticker} does not have OHLCV data.")
            return None


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    def etf_profile_api_call_to_file(self):
        """
        Calls the AlphaVantage API to retrieve ETF profile data.
        """
        # AlphaVantage API call
        json_data = make_alphavantage_api_call(self.ticker,'etf')
        if not json_data or not isinstance(json_data, dict):
            return None

        jsonkeys = [*json_data.keys()]
        if not jsonkeys or jsonkeys == []:
            print(f"{self.ticker} does not have ETF profile data.")
            return None

        # set the file path for the ETF profile data (does not require subdirectory)
        try:
            etf_path = self.ts.ticker_file_pathways(self.ticker)
            etf_profile = etf_path.get('etf')
        except AttributeError as ae:
            print(f"Filepathway for {self.ticker} unable to be created. {ae}")
            return None
        if not etf_profile or not isinstance(etf_profile, str):
            return None

        etf_dir = os.path.dirname(etf_profile)

        # make sure there is a directory for the ETF profile data
        if not etf_dir or not os.path.isdir(etf_dir):
            os.makedirs(etf_dir, exist_ok=True)

            # write the data to file
            with open(etf_profile, 'w') as jsonfile:
                json.dump(json_data, jsonfile)

        elif os.path.isfile(etf_profile) and os.stat(etf_profile).st_size:
            local_data = load_json_from_file_safe(etf_profile)
            if local_data == json_data:
                print(f"ETF profile data for {self.ticker} is up to date.")
                return None
            else:
                with open(etf_profile, 'w') as jsonfile:
                    json.dump(json_data, jsonfile)

        if os.path.exists(etf_profile) and os.stat(etf_profile).st_size:
            print(f"ETF profile data for {self.ticker} updated.")
        else:
            print(f"{self.ticker} does not have ETF profile information.")
            return None


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    def financials_api_call_to_file(self,key:str):
        """
        Calls the AlphaVantage API to retrieve financial statement data and saves it to files.
        :param key: The type of financial statement to retrieve ('earnings', 'balance', 'cash', 'income').
        :return: None
        """
        # verify the keys are correct
        if key in ['earnings', 'balance', 'cash', 'income']:
            # unlike the other api calls, you'll need the keys first, then the file paths for inside the key pathway
            json_data = make_alphavantage_api_call(self.ticker, key)
        else:
            print(f"Invalid key: {key}")
            return None

        k = None # k is an object used to tell the next loop not to bother if the key came back w/ no info

        if not json_data:
            k = False
            return k

        # create the properly named file keys for the financial statement data
        if key != 'earnings':
            annual_key, quarterly_key = 'annualReports', 'quarterlyReports'
        else:
            annual_key, quarterly_key = 'annualEarnings', 'quarterlyEarnings'

        if annual_key in json_data and quarterly_key in json_data:
            annual = json_data.get(annual_key)
            quarterly = json_data.get(quarterly_key)

            # file pathways
            try:
                fin_path = self.ts.ticker_file_pathways(self.ticker)
                fin_path = fin_path.get(key, {})
            except AttributeError as ae:
                print(f"No filepathway dictionary was able to be created for {self.ticker}. {ae}")
                return None
            if not fin_path or not isinstance(fin_path, dict) or fin_path == {}:
                print(f"{self.ticker} has no data for {key}")
                return None

            afp = fin_path.get('annual', '')
            qfp = fin_path.get('quarterly', '')

            fin_dir = os.path.dirname(afp)

            # make sure there is a directory for the financial statements
            if not os.path.isdir(fin_dir):
                os.makedirs(fin_dir, exist_ok=True)

            if annual:
                with open(afp, 'w') as jsonfile:
                    json.dump(annual, jsonfile)
            if quarterly:
                with open(qfp, 'w') as jsonfile:
                    json.dump(quarterly, jsonfile)

        else:
            print(f"No {self.ticker} data for {key} within the called upon information")
            k = False
            return k
        if os.path.exists(afp) and os.stat(afp).st_size:
            print(f"{key} data for {self.ticker} saved to file")
            return None
        else:
            print(f"{self.ticker} {key} data did not save to file.")
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _check_financial_files_recently_modified(self, days_threshold: int = 90) -> bool:


        """
        Check if any financial statement files for this ticker have been modified
        within the specified number of days.
        :param days_threshold: Number of days to check (default 90)
        :return: True if files were recently modified, False otherwise
        """
        try:
            fin_paths = self.ts.ticker_file_pathways(self.ticker)
            if not fin_paths or not isinstance(fin_paths, dict):
                return False

            today = dt.date.today()
            for key in ['balance', 'cash', 'income', 'earnings']:
                if key in fin_paths and isinstance(fin_paths[key], dict):
                    for period_type in ['annual', 'quarterly']:
                        file_path = fin_paths[key].get(period_type)
                        if file_path and isinstance(file_path, str) and os.path.isfile(file_path):
                            mod_time = os.path.getmtime(file_path)
                            mod_date = dt.date.fromtimestamp(mod_time)
                            days_old = (today - mod_date).days
                            if days_old <= days_threshold:
                                print(
                                    f"{self.ticker} {key} {period_type} file modified {days_old} days ago (within {days_threshold} day threshold)")
                                return True
            return False
        except Exception as e:
            print(f"Error checking file modification times for {self.ticker}: {e}")
            return False


    def update_securities_data(self):
        """
        Checks the database for the most recent data and determines if updates are needed.
        - OHLCV: weekly update (7+ days since last price date in DB)
        - Quarterly financials: check after 30 days past quarter end
        - Annual financials: check after 30-60 days past fiscal year end
        - Company details: refreshed alongside financial updates
        Downloads new data from AlphaVantage, saves to file, and updates the database.
        """
        from Securities_DB.create_database import (
            update_ohlcv_for_ticker, update_company_details_for_ticker,
            update_financials_for_ticker, update_market_capitalization_for_ticker
        )

        if not isinstance(self.ticker, str):
            raise TypeError('ticker must be a string')

        cd = CD(self.ticker)
        today = dt.date.today()

        # ── 1. Weekly OHLCV update ───────────────────────────────────────
        try:
            from data_access.OHLCVPriceData import OHLCVPriceData

            ohlcv_db = OHLCVPriceData(self.ticker)
            latest = ohlcv_db.latest_price()
            date = latest.get('date','')
            latest_price = latest.get('close', None)
        except Exception:
            print(f"No latest price data found for {self.ticker}")

        if latest_price and date and date != '':
            last_price_date = dt.datetime.fromisoformat(str(latest_price['date'])[:10])
            ohlcv_age = (today - last_price_date).days
        else:
            ohlcv_age = 999  # no data, force download

        if ohlcv_age >= 7:
            print(f"OHLCV for {self.ticker} is {ohlcv_age} days old. Downloading...")
            self.price_history_api_call_to_file()
            update_ohlcv_for_ticker(self.ticker)
        else:
            print(f"OHLCV for {self.ticker} is up to date (last price: {latest_price.get('date', 'N/A')})")

        # ── 2. Financial statement updates (stocks only, not ETFs) ────────
        details = cd.get_details()
        if not details or details.get('AssetType') not in ('Common Stock', 'Equity'):
            print(f"{self.ticker} is not a common stock; skipping financial updates.")
            return None

        # determine fiscal year end month
        fiscal_year_end = details.get('FiscalYearEnd')  # e.g. 'December'
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12
        }
        fy_month = month_map.get(fiscal_year_end, 12) if fiscal_year_end else 12

        # ── 2a. Quarterly financial reports ───────────────────────────────
        latest_q_date_str = cd.get_latest_quarterly_fiscal_date()
        need_quarterly = False

        if latest_q_date_str:
            latest_q_date = dt.datetime.fromisoformat(latest_q_date_str)
            # next quarter end is ~3 months after the last one
            next_q_end = latest_q_date + dt.timedelta(days=90)
            # check 30 days after expected quarter end (SEC allows up to 45)
            check_date = next_q_end + dt.timedelta(days=30)
            # check the last time the file was modified
            cd_last_qdate = cd.get_latest_quarter()
            if cd_last_qdate != latest_q_date_str:
                need_quarterly = True
                cd_last_qdt = dt.datetime.fromisoformat(cd_last_qdate)
                if today >= cd_last_qdt + dt.timedelta(days=91):
                    print(f"Quarterly reports for {self.ticker}: last quarter ended {latest_q_date_str}")
            if today >= check_date:
                # check if files were modified within the 90-day quarter period
                files_recently_modified = self._check_financial_files_recently_modified(days_threshold=90)
                if not files_recently_modified:
                    need_quarterly = True
                    print(f"Quarterly reports for {self.ticker}: last quarter ended {latest_q_date_str}, "
                          f"checking for new data (30+ days past expected next quarter)...")
                else:
                    print(f"Quarterly reports for {self.ticker}: files recently updated, skipping API call.")
        else:
            need_quarterly = True
            print(f"No quarterly financial data for {self.ticker} in DB. Downloading...")

        # ── 2b. Annual financial reports ──────────────────────────────────
        latest_a_date_str = cd.get_latest_annual_fiscal_date()
        need_annual = False
        if latest_a_date_str:
            latest_a_date = dt.date.fromisoformat(latest_a_date_str)
            # next annual report expected at fiscal year end
            next_fy_end = dt.date(latest_a_date.year + 1, fy_month, 28)
            # check 30 days after fiscal year end (SEC allows 60-90)
            check_date_early = next_fy_end + dt.timedelta(days=30)
            check_date_late = next_fy_end + dt.timedelta(days=60)
            if today >= check_date_early:
                # check if files were modified within the 90-day period
                files_recently_modified = self._check_financial_files_recently_modified(days_threshold=90)
                if not files_recently_modified:
                    need_annual = True
                    status = "30+ days" if today < check_date_late else "60+ days"
                    print(f"Annual reports for {self.ticker}: last FY ended {latest_a_date_str}, "
                          f"{status} past expected new FY end. Downloading...")
                else:
                    print(f"Annual reports for {self.ticker}: files recently updated, skipping API call.")
            else:
                print(f"Annual reports for {self.ticker}: latest annual date {latest_a_date_str}; "
                      f"next check date is {check_date_early.isoformat()}.")
        else:
            need_annual = True
            print(f"No annual financial data for {self.ticker} in DB. Downloading...")

        # ── 2c. Download and update DB if needed ──────────────────────────
        if need_quarterly or need_annual:
            # refresh company details first (updates LatestQuarter etc.)
            company_details = self.company_details_api_call()
            company_details_path = self.ts.ticker_file_pathways(self.ticker).get('company_details')
            if company_details and isinstance(company_details_path, str):
                company_details_dir = os.path.dirname(company_details_path)
                if company_details_dir and not os.path.isdir(company_details_dir):
                    os.makedirs(company_details_dir, exist_ok=True)
                with open(company_details_path, 'w') as jsonfile:
                    json.dump(company_details, jsonfile)
            update_company_details_for_ticker(self.ticker)

            # download all financial statements (API returns both annual + quarterly)
            for fin_key in ['balance', 'cash', 'income', 'earnings']:
                print(f"Downloading {fin_key} statements for {self.ticker}...")
                self.financials_api_call_to_file(fin_key)

            # update the database with new file data
            update_financials_for_ticker(self.ticker)
            print(f"Financial data for {self.ticker} updated in database.")
        else:
            print(f"Financial data for {self.ticker} is up to date.")

        # ── 3. Update market capitalization ───────────────────────────────
        update_market_capitalization_for_ticker(self.ticker)

        return None
