# Investment Maintenance Jobs

## Update local securities

Run the recurring update job from the project root:

```bash
python3 scripts/update_securities.py
```

Useful safer runs:

```bash
python3 scripts/update_securities.py --dry-run --max-existing 5 --max-new 2
python3 scripts/update_securities.py AAPL SPY
```

The updater:

- Updates securities already downloaded under `Securities/` and `ETF_Securities/`.
- Compares the latest `company_tickers.json` with the previous SEC registry state.
- Bootstraps only tickers newly seen since the prior registry sync unless
  `--bootstrap-new-from-sec` is passed.
- Creates local tracking tables in `Securities_DB/investment.db`, including
  `inactive_security_symbols` for delisted/removed symbols, failed tickers, and
  tickers where an update completed without changing local files.

For scheduled runs, point cron or launchd at the same command from the project
root. Long Alpha Vantage runs can be split with `--max-existing` and `--max-new`.

## Backfill adjusted prices only

Use the dedicated runner when financial statements and company details should
not be refreshed:

```bash
python3 scripts/backfill_adjusted_prices.py --magic-formula --limit 100
python3 scripts/backfill_adjusted_prices.py --magic-formula --limit 100 --execute
```

The first command is review-only. Executed runs skip tickers whose stored daily
rows already have complete adjusted coverage, verify coverage after each load,
and write resumable run/event records to `investment.db`. Use repeated
`--exclude-ticker` options only for a source anomaly that has already been
reviewed and recorded.
