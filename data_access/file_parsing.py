from pathlib import Path
import shutil
import os
import json
import csv
from runtime_config import get_data_root

#_______________________________________________________________________________________________________________
#                                ALPHAVANTAGE API CALL FUNCTIONS
#____________________________________________________________________________________________
#____________________________________________________________________________________________
#           FILE PARSING FUNCTIONS FOR THE PURPOSE OF FILE CREATION AND VERIFICATION
#____________________________________________________________________________________________


def valid_etf_tickers_to_file()->list:
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
    if valid_etf:
        with open(os.path.join(get_data_root(), 'valid_etf_tickers.csv'),'w',newline='') as tp:
            writer = csv.writer(tp,delimiter=',')
            writer.writerow(valid_etf)
    if os.path.isfile(os.path.join(get_data_root(), 'valid_etf_tickers.csv')):
        return print(f"{len(valid_etf)} valid ETF tickers saved to file.")
    else:
        return None


def valid_etf_tickers()->list:
    with open(os.path.join(get_data_root(), 'valid_etf_tickers.csv')) as tp:
        reader = csv.reader(tp,delimiter=',')
        etflist = [row for row in reader][0]
    return etflist

def tickers_titles()->dict:
    fp = os.path.join(get_data_root(), 'company_tickers.json')
    return load_json_from_file_safe(fp) if os.path.isfile(fp) else None


def get_all_ticker_symbols()->list:
    """Retrieve all ticker symbols from company_tickers.json and return as a list."""
    cmp_tkrs = os.path.join(get_data_root(), 'company_tickers.json')
    with open(cmp_tkrs) as f:
        data = json.load(f)
    all_ticker_symbols = [data['ticker'] for idx,data in data.items() if idx.isnumeric()]
    return all_ticker_symbols


def all_tickers_to_file_writer()->None:
    """Write all ticker symbols to a csv file."""
    all_ticker_symbols = get_all_ticker_symbols()
    ticker_path = os.path.join(get_data_root(), 'all_ticker_symbols.csv')
    with open(ticker_path,'w',newline='') as tp:
        writer = csv.writer(tp,delimiter=',')
        writer.writerow(all_ticker_symbols)
    return None


def valid_ticker_list()->list:
    """Read all ticker symbols from a csv file and return as a list."""
    # iterate through the ticker_search_info directory
    search_dic = os.path.join(get_data_root(), 'All_Tickers_Searched')
    iter_files = os.scandir(search_dic)
    # create a list to store the ticker symbols
    valid_tickers = []
    for file in iter_files:
        if os.stat(file).st_size:
            valid_tickers.append(file.name.split('_')[0])

    return valid_tickers


def magic_formula_ticker_list():
    with open(os.path.join(get_data_root(), 'magic_formula_tickers.csv'), 'r') as file:
        magic_tickers = file.readlines()
        magic_tickers = magic_tickers[0].split(',')

    return magic_tickers


def all_securities_search_info_directory_builder()->None:
    """Build a directory structure for all securities search information."""
    all_ticker_symbols = get_all_ticker_symbols()
    tickers_searched = {ticker: None for ticker in all_ticker_symbols if not any((ticker == '.', ticker == '', None))}
    path = os.path.join(get_data_root(), 'All_Tickers_Searched')
    if not os.path.isdir(path):
        os.mkdir(path)

    for ticker in tickers_searched.keys():
        if not any((ticker == '.', ticker == '', None)):
            suffix = f'{ticker}_ticker_search_info.json'
            path = Path(path)
            file_path = path / suffix
            file_path.touch(exist_ok=True)
    return None


def remove_old_securities_search_info_files()->None:
    """Remove all ticker search information files from the old directory structure."""
    etfroot = Path(get_data_root()) / 'ETF_Securities'
    cmnstkroot = Path(get_data_root()) / 'Securities'
    curr_dir_structure_path = Path(get_data_root()) / 'All_Tickers_Searched'

    # get lists of the file paths needed to check against the new structure
    cmnstk_fp = [fp for fp in cmnstkroot.iterdir() if not fp.name.startswith('.')]
    etf_fp = [fp for fp in etfroot.iterdir() if not fp.name.startswith('.')]
    all_sec_fp = cmnstk_fp + etf_fp

    # loop through all security file paths and move them to the new directory structure
    for fp in all_sec_fp:
        # determine if the file is in the old directory structure
        if fp.parent.name == 'ETF_Securities':
            ticker = fp.name.split('__')[0]
            path = etfroot / fp / 'ticker_search_info.json'
            if os.path.isfile(path):
                new_path = curr_dir_structure_path / f'{ticker}_ticker_search_info.json'
                shutil.move(path, new_path)
                # if it works, remove the old file
                if new_path.is_file():
                    shutil.rmtree(path)
                    print(f'{new_path} moved successfully.{path} removed')
                else:
                    print(f'Failed to move {path} to {new_path}')
        elif fp.parent.name == 'Securities':
            ticker = fp.name.split('__')[0]
            path = cmnstkroot / fp / 'ticker_search_info.json'
            if os.path.isfile(path):
                new_path = curr_dir_structure_path / f'{ticker}_ticker_search_info.json'
                shutil.move(path, new_path)
                # if it works, remove the old file
                if new_path.is_file():
                    shutil.rmtree(path)
                    print(f'{new_path} moved successfully.{path} removed')
                else:
                    print(f'Failed to move {path} to {new_path}')
        else:
            print(f'File {fp} is not in the expected directory structure.')
    return None


# def no_info_ticker_search_info_synbols_to_file()->None:
#     """
#     run this function when a new ticker symbol list is obtained from the SEC website. This should be run after the
#     new list is run against the old list. Any new tickers should be checked to see if they have valid ticker search
#     information. This can be done by running the keys of 'valid tickers' against 'bad tickers' and the new symbols.
#     """
#     bad_tickers = TS().no_ticker_info_symbols_list()
#     bad_path = Path('no_ticker_search_info_ticker_symbols.csv')
#     with open(bad_path, 'w', newline='') as tp:
#         writer = csv.writer(tp, delimiter=',')
#         writer.writerow(bad_tickers)
#
#     print(f"{len(bad_tickers)} ticker symbols returned no search information from AlphaVantage 'ticker_symbol_search'.")
#     return None

# def update_file(fp: str, ticker: str, key: str = None):
#     """
#     Checks if a file is older than 7 days.
#     If so, downloads new data using existing project functions.
#     """
#     try:
#         if not isinstance(ticker, str):
#             raise TypeError('symbol must be a string')
#         if key not in ('balance', 'cash', 'income', 'earnings', 'ohlcv', 'company_details', 'etf'):
#             raise ValueError(
#                 f"{key} must be 'balance','cash','income','earnings','ohlcv', 'company_details', or 'etf'.")
#     except (TypeError, ValueError) as v:
#         print(v)
#
#     if not os.path.isfile(fp):
#         raise FileNotFoundError(f"{fp} does not exist.")
#     else:
#         # Get last modified time
#         mtime = os.path.getmtime(fp)
#         last_modified_date = dt.date.fromtimestamp(mtime)
#         today = dt.date.today()
#         # Calculate difference in days
#         delta = today - last_modified_date
#
#         if delta.days >= 7 and key == 'ohlcv':
#             print(f"File for {ticker} is {delta.days} days old. Updating...")
#             # Download new information
#             financial_statements(ticker, key)
#
#         elif delta.days >= 30 and key != 'ohlcv':
#             print(f"File for {ticker} is {delta.days} days old. Updating...")
#             # Download new information
#             financial_statements(ticker, key)
#
#         elif delta.days < 7 and key == 'ohlcv':
#             print(f"File for {ticker} is up to date (last modified {last_modified_date}).")
#
#         elif delta.days < 30 and key != 'ohlcv':
#             print(f"File for {ticker} is up to date (last modified {last_modified_date}).")
#
#     return None

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


# created w/ AI for error handling JSON files
def load_json_from_file_safe(path, *,verbose=True):
    """
    Safely load JSON file. Returns None if the file is missing, emtpy, or invalid
    :rtype: Any | None
    """
    if not path or not isinstance(path, str):
        if verbose:
            print(f"Invalid path: {path}")
        return None

    if not os.path.isfile(path):
        if verbose:
            print(f"Missing file: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                if verbose:
                    print(f"Blank JSON file: {path}")
                return None
            return json.loads(content)
    except json.JSONDecodeError as e:
        if verbose:
            print(f"Invalid JSON in {path}: {e}")
        return None
    except OSError as e:
        if verbose:
            print(f"File read error for {path}: {e}")
        return None


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def load_etf_profile_data_to_file():
    from data_ingestion.TickerFileSearch import TickerSearch as TS

    valid_etf = TS().valid_etf_tickers()
    valid_dirs = {etf:str for etf in valid_etf if etf}

    etf_dir = os.path.join(get_data_root(), 'ETF_Securities')

    for fp in os.scandir(etf_dir):
        if not fp or fp.name.startswith('.'):
            continue
        name = fp.name.split('__')[0]
        if name in valid_dirs:
            valid_dirs[name] = fp.path

    for etf in valid_etf:
        # initial checks
        if not etf or etf.startswith('.'):
            continue
        # make sure there is data present
        if valid_dirs.get(etf) is None or valid_dirs.get(etf) != {}:
            print(f"{etf} is missing profile data.")
            continue
        # objectify the data
        _etf_data = valid_dirs.get(etf)

        ts = TS().ticker_file_pathways(etf)
        if not ts or not isinstance(ts,dict):
            continue
        # etf_profile file pathway and directory name
        file_dir = os.path.dirname(ts.get('etf'))
        _fp = ts.get('etf')

        if not _fp or not isinstance(_fp,str):
            print(f"{etf} did not load pathway properly or it was an incorrect pathway.")
            continue

        if not os.path.isdir(file_dir):
            # if it isn't created, create it
            os.makedirs(file_dir,exist_ok=True)
            print(f"Creating etf_profile for {etf}")

            # place the etf_profile data into the directory
            with open(_fp,'w') as _etf_file:
                json.dump(_etf_data,_etf_file)
            # verify it loaded properly
            if os.path.isfile(_fp) and os.stat(_fp).st_size:
                print(f"******{etf}: {_fp}")

        if not os.path.isdir(file_dir):
            print(f"{etf} directory couldn't be created")
            continue

        elif os.path.isdir(file_dir):
            valid_dirs[etf] = file_dir
            # see if the directory has anything in it
            if os.stat(file_dir).st_size:
                # if so ...
                _dirlist = os.listdir(file_dir)
                # create a fp object
                new_fp = None
                # loopy loop
                for _dir in _dirlist:
                    # get the etf_profile.json file if it's there
                    if _dir.endswith('.json'):
                        new_fp = os.path.join(file_dir, _dir)
                        break
                # was it there
                if new_fp and os.stat(new_fp).st_size and new_fp == _fp:
                    print(f"*******{etf}: {_fp}")
                else:
                    # place the file the directory
                    print(f"Creating etf_profile for {etf}")
                    with open(_fp,'w') as _etf_file:
                        json.dump(_etf_data,_etf_file)
                    if os.path.isfile(_fp) and os.stat(_fp).st_size:
                        print(f"******{etf}: {_fp}")
            else:
                print(f"Creating etf_profile for {etf}")
                with open(_fp,'w') as _etf_file:
                    json.dump(_etf_data,_etf_file)
                if os.path.isfile(_fp) and os.stat(_fp).st_size:
                    print(f"******{etf}: {_fp}")
        else:
            print(f"{etf} is not a valid etf???")



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def load_etf_ohlcv_data_to_file():
    from data_ingestion.DataExtraction import DataExtraction as DE
    from data_ingestion.TickerFileSearch import TickerSearch as TS
    # etf directory
    etf_dir = os.path.join(get_data_root(), 'ETF_Securities')

    for edir in os.scandir(etf_dir):
        ohlcv_dir = False
        if os.path.isdir(edir.path):
            for obj in os.scandir(edir.path):
                if 'OHLCV' in obj.name:
                    ohlcv_dir = True
                    break
        if not ohlcv_dir and not os.path.isfile(edir.path):
            ticker = edir.name.split('__')[0]
            print(f"{ticker} has no OHLCV directory.")
            de = DE(ticker=ticker)
            de.price_history_api_call_to_file()
            fp = TS().ticker_file_pathways(ticker)
            if not fp or not isinstance(fp, dict):
                continue
            fp = fp['ohlcv']
            fp = fp['price_hx'] if fp else None

            if fp and os.path.isfile(fp):
                print(f"{ticker} OHLCV directory created and price history downloaded.")
            else:
                print(f"\n{ticker} does not have OHLCV data.\n")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
