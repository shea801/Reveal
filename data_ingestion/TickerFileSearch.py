# Python 3.14
# created: March 25, 2026
# UPDATED: March 26, 2026

import os
from data_access.file_parsing import load_json_from_file_safe
from runtime_config import get_data_root


class TickerSearch:
    def __init__(self):
        pass

    def tickers_titles(self) -> dict:
        """Retrieve the ticker symbols and company names from the company_tickers.json file."""
        cmp_tkrs = os.path.join(get_data_root(), 'company_tickers.json')
        t_n_t = load_json_from_file_safe(cmp_tkrs) if os.path.isfile(cmp_tkrs) else None
        cmp_tkrs = ''
        return t_n_t

    def all_ticker_symbols(self) -> list:
        """Retrieve all ticker symbols from company_tickers.json and return as a list."""
        tickers_and_titles = self.tickers_titles()
        all_ticker_symbols = [value['ticker'] for key,value in tickers_and_titles.items() if key.isnumeric()]

        return all_ticker_symbols

    def securities_ticker_search_information(self) -> dict:
        """"
        Return a dictionary with every ticker symbol as a key and the ticker search information as the value.
        If .value() is None, it means the file was never, downloaded, found, or returned as None from the
        symbol_search_api_call() function.
        """
        # get all the ticker symbols...
        all_tickers = self.all_ticker_symbols()
        # create a dictionary with the ticker symbols as keys and None as the starting values
        tickers_searched = {ticker: None for ticker in all_tickers if ticker}

        # loopy loop
        for ticker in all_tickers:
            data = self.ticker_search_information(ticker)
            if data:
                tickers_searched[ticker] = data
        return tickers_searched

    def valid_tickers_symbol_list(self) -> list:
        """Return a list of ticker symbols that have valid ticker search information."""
        # iterate through the ticker_search_info directory
        search_dic = os.path.join(get_data_root(), 'All_Tickers_Searched')
        iter_files = os.scandir(search_dic)
        # create a list to store the ticker symbols
        valid_tickers = []
        for file in iter_files:
            if os.stat(file.path).st_size:
                valid_tickers.append(file.name.split('_')[0])
        file = ''
        search_dic = ''
        return valid_tickers

    def valid_etf_tickers(self)->list:
        etf_dir = os.path.join(get_data_root(), 'ETF_Securities')
        valid_etf = []
        for fp in os.scandir(etf_dir):
            if not fp or fp.name.startswith('.'):
                continue
            if fp.is_dir():
                for _fp in os.scandir(fp.path):
                    if _fp.name.endswith('.json'):
                        ticker = fp.name.split('__')[0]
                        valid_etf.append(ticker)
                        break
        etf_dir = ''
        fp = ''
        _fp = ''
        if valid_etf:
            return valid_etf
        else:
            return []


    def valid_common_stock_tickers(self)->list:
        sec_dir = os.path.join(get_data_root(), 'Securities')
        valid_stocks = []
        for fp in os.scandir(sec_dir):
            if not fp or fp.name.startswith('.'):
                continue
            if fp.is_dir():
                for sub_fp in os.scandir(fp.path):
                    if sub_fp.name.endswith('.json'):
                        if os.path.isfile(sub_fp.path):
                            ticker = fp.name.split('__')[0]
                            valid_stocks.append(ticker)
                            break
        sec_dir = ''
        fp = ''
        sub_fp = ''

        if valid_stocks:
            return valid_stocks
        else:
            return []

    # def vetted_magic_formula_symbols(self):
    #     with open('vetted_magic_formula_symbols.csv', 'r', newline='') as file:
    #         reader = csv.reader(file)
    #         vetted = [*reader][0]
    #     return vetted


    def no_ticker_info_symbols_list(self) -> list:
        """Return a list of ticker symbols that do not have ticker search information."""
        no_info_tickers = []
        search_dict = self.securities_ticker_search_information().items()
        for ticker, data in search_dict:
            if not data:
                no_info_tickers.append(ticker)

        return no_info_tickers

    def is_ticker_valid(self, ticker:str) -> bool:
        """Validate if a ticker symbol is in the list of all ticker symbols."""
        # check the argument type
        assert isinstance(ticker, str), "Ticker argument must be a string."
        # all tickers registered to the SEC's EDGAR database via the SEC's ticker search file'
        all_tickers = self.all_ticker_symbols()
        # yay or nay?
        exists = ticker.upper() in all_tickers
        return exists

    def ticker_file_pathways(self, ticker:str) -> dict:
        """
        This class method will return a dictionary with the pathways paired to the appropriate data
        file (i.e., the key 'balance' will return a dictionary of file pathways using keys annual and quarterly,
        respectively, whereas 'search_info' key returns a string file pathway to the 'ticker_search_info.json' file).
        The keys present are: 'search_info', 'OHLCV', and depending on whether the security is a
        common stock or an ETF 'company_details', 'balance', 'income', and 'cashflow' for common stocks and
        'etf_profile' for ETFs.

        IT DOES NOT CREATE THE FILE PATHWAYS, OR THE FILES, OR DIRECTORIES THEMSELVES. JUST
        WHAT THE PATHWAYS WOULD BE IF THE FILES WERE TO BE CREATED.
        """
        assert isinstance(ticker, str), 'symbol must be a string'
        if not ticker.isupper():
            ticker = ticker.upper()

        # the dictionary holding either false if no path, or the path if it exists
        full_file_pathways = {
            'ticker_search': None,
            'ohlcv': None | dict,
            'company_details': None,
            'etf': None,
            'balance': None | dict,
            'cash': None | dict,
            'income': None | dict,
            'earnings': None | dict,
        }
        # directories and subdirectories
        root = get_data_root()

        # get the securities ticker symbol and company name from the SEC provided file for currently listed securities.
        tickers_and_names = self.tickers_titles()
        if not tickers_and_names:
            return full_file_pathways

        t_and_n = {
            value['ticker']:value['title'] for key,value in tickers_and_names.items() if key.isnumeric()
        }

        ticker_search_path = os.path.join(root, 'All_Tickers_Searched')
        etf_dir = os.path.join(root, 'ETF_Securities')
        sec_dir = os.path.join(root, 'Securities')

        # file pathway
        t_s_path = f'{ticker}_ticker_search_info.json'
        tsp = os.path.join(ticker_search_path, t_s_path)

        if not os.path.isfile(tsp) or not os.stat(tsp).st_size:
            return full_file_pathways

        full_file_pathways['ticker_search'] = tsp

        # It there's no title, prevent it from crashing
        title = t_and_n.get(ticker)
        if not title:
            return full_file_pathways
        sub_dir = f'{ticker}__{title}'

        # try and load the ticker_search_info file
        data = load_json_from_file_safe(tsp)

        if not data:
            return full_file_pathways

        if data.get('3. type') == 'Equity':
            # set the parent directory
            parent_dir = os.path.join(sec_dir, sub_dir)

            # company details file pathway
            company_details = os.path.join(parent_dir, 'current_company_details.json')
            full_file_pathways['company_details'] = company_details

            # OHLCV directory
            ohlcv = os.path.join(parent_dir, 'OHLCV')
            price_hx = os.path.join(ohlcv, f'{ticker}ohlcv.json')
            meta = os.path.join(ohlcv, f'{ticker}meta.json')

            full_file_pathways['ohlcv'] = {'price_hx':price_hx, 'meta_data':meta}

            # Financial_Statements directory
            fin_sttmnts = os.path.join(parent_dir, 'Financial_Statements')

            for key in ('balance', 'cash', 'income', 'earnings'):
                k = 'Cash_Flow' if key == 'cash' else key.title()
                childir = os.path.join(fin_sttmnts, k)
                if key != 'earnings':
                    annreports = os.path.join(childir, f'{k}AnnualReports.json')
                    qrtreprorts = os.path.join(childir, f'{k}QuarterlyReports.json')

                    full_file_pathways[key] = {'annual': annreports, 'quarterly': qrtreprorts}

                else:
                    annearn = os.path.join(childir, f'{k}AnnualEarnings.json')
                    qrtearn = os.path.join(childir, f'{k}QuarterlyEarnings.json')

                    full_file_pathways[key] = {'annual': annearn, 'quarterly': qrtearn}

        elif data.get('3. type') == 'ETF':
            # set the parent directory
            parent_dir= os.path.join(etf_dir, sub_dir)

            # verify if the ticker symbol is the same as the ticker symbol in the file
            if ticker != data.get('1. symbol'):
                return full_file_pathways

            # create the price history file pathway
            ohlcv_dir = os.path.join(parent_dir, 'OHLCV')
            ohlcv = os.path.join(ohlcv_dir, f'{ticker}ohlcv.json')
            meta = os.path.join(ohlcv_dir, f'{ticker}meta.json')

            full_file_pathways['ohlcv'] = {'price_hx':ohlcv, 'meta_data':meta}

            etf_profile = os.path.join(parent_dir, f'{ticker}_etf_profile.json')
            full_file_pathways['etf'] = etf_profile
        else:
            print(f'Failed to create securities directory for {ticker}.')

        return full_file_pathways

    # this method will return the JSON file as a dictionary containing the 'ticker_search_info'
    def ticker_search_information(self, ticker: str) -> dict:
        """
        Returns the JSON file as a dictionary containing the 'ticker_search_info' for the given ticker symbol.
        If the ticker symbol is not valid or the JSON file does not exist, returns None.
        """

        assert isinstance(ticker, str), "Ticker argument must be a string"

        if not ticker.isupper():
            ticker = ticker.upper()

        all_tickers = self.all_ticker_symbols()

        if ticker not in all_tickers:
            return None
        else:
            # account for the ticker being in the active list, and not a delisted ticker symbol
            child = f'{ticker}_ticker_search_info.json'
            root_dir = os.path.join(get_data_root(), 'All_Tickers_Searched')
            fp = os.path.join(root_dir, child)
            if os.path.isfile(fp) and os.stat(fp).st_size:
                data = load_json_from_file_safe(fp)
                root_dir = ''
                fp = ''
                return data
            else:
                root_dir = ''
                fp = ''
                return {}

    def ticker_data_present(self,ticker:str):
        """"
            This function checks if a security's file status. If the security has data of relative a
            type, each key will return a stringified file pathway, otherwise, the key will return False.
            The function returns a dictionary with the following keys:
                {'equity': {{fin_statements:<file pathway>},ticker_search:<file pathway>},
                 'etf: {{etf_profile:<file pathway>},ticker_search:<file pathway>},},
                 'ohlcv': <file pathway>, 'etf': <file pathway>}
            """

        assert isinstance(ticker, str), "Ticker argument must be a string."
        if not ticker.isupper():
            ticker = ticker.upper()

        _data_present: dict = {
            'ticker_search': False,
            'ohlcv': False,
            'company_details': False,
            'etf_profile': False,
            'balance': False,
            'cash': False,
            'income': False,
            'earnings': False,
        }

        pathways = self.ticker_file_pathways(ticker)
        tickersearch_path = pathways.get('ticker_search')

        if not tickersearch_path or not os.path.isfile(tickersearch_path) or os.stat(tickersearch_path).st_size < 2:
            return _data_present

        tickersearch = load_json_from_file_safe(tickersearch_path)
        if not isinstance(tickersearch, dict) or not tickersearch:
            return _data_present

        tickersearch_keys = [key for key in tickersearch.keys() if not any((key.startswith('.'),'',None))]
        required_keys = {'1. symbol', '2. name', '3. type'}

        if not required_keys.issubset(tickersearch_keys):
            return _data_present

        if tickersearch.get('1. symbol') != ticker:
            if tickersearch.get('2. name') == ticker.title():
                pass
            else:
                return _data_present

        _data_present['ticker_search'] = True

        if tickersearch['3. type'] == 'ETF':
            etf_profile_path = pathways.get('etf')
            if etf_profile_path and os.path.isfile(etf_profile_path):
                _data_present['etf_profile'] = True

            ohlcv_paths = pathways.get('ohlcv')
            if isinstance(ohlcv_paths, dict):
                price_hx = ohlcv_paths.get('price_hx')
                if price_hx and os.path.isfile(price_hx):
                    _data_present['ohlcv'] = True

            return _data_present

        elif tickersearch['3. type'] == 'Equity':
            company_details_path = pathways.get('company_details')
            if company_details_path and os.path.isfile(company_details_path):
                _data_present['company_details'] = True

            for key in ('ohlcv', 'balance', 'cash', 'income', 'earnings'):
                file_paths = pathways.get(key)
                if isinstance(file_paths, dict) and len(file_paths):
                    if key != 'ohlcv':
                        p1 = file_paths.get('annual')
                        p2 = file_paths.get('quarterly')
                    else:
                        p1 = file_paths.get('price_hx')
                        p2 = file_paths.get('meta_data')
                    if p1 and p2 and os.path.isfile(p1) and os.path.isfile(p2):
                        _data_present[key] = True

            return _data_present

        else:
            return _data_present
