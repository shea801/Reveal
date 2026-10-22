# Magic Formula Backtesting

## Purpose

This document describes Reveal’s historical Magic Formula backtesting
workflow.

The backtest exists primarily to validate historical ranking and
data-handling mechanics. It should not be interpreted as proof that the
strategy will produce future returns.

The workflow is designed to reduce look-ahead bias by combining:

- historical Magic Formula ranking data;
- SEC filing-availability metadata;
- ticker/CIK identity rules;
- a common information cutoff;
- a common market-price session; and
- adjusted prices for return measurement.

## Strategy Under Test

The project’s Magic Formula implementation ranks eligible common stocks
using two independently ranked metrics:

1.  Return on Capital (ROC)
2.  Earnings Yield (EY)

The ordinal ROC rank and Earnings Yield rank are added. The lowest
combined score receives the strongest Magic Formula rank.

The historical rank database stores ranking information rather than
duplicating raw financial or market-price values.

## Historical Ranking Data

Magic Formula results are stored by ticker and quarter.

The ranking store includes:

- ticker;
- quarter date;
- associated annual date;
- financial-statement availability date where applicable;
- Magic Formula rank;
- Return on Capital rank;
- Earnings Yield rank; and
- combined ROC/EY ordinal score.

Financial values and prices remain in their source analytical and
database layers.

## Point-in-Time Qualification

A historical ranking row is not automatically eligible for a strict
backtest.

The workflow verifies the financial information required for the
simulated decision using the SEC metadata layer described in
`SEC_POINT_IN_TIME.md`.

Strict analysis rejects securities when required filing matches or
historical identity cannot be established to the required confidence.

## Common Information Cutoff

The backtest determines a common information cutoff for the cohort.

This prevents individual securities from being valued using different
amounts of future information merely because their filing dates differ.

After the required information is available, the workflow selects the
next common trading session for the cohort.

## Reranking at a Common Market Date

The historical source cohort is reranked using the same market-price
date.

This distinction matters because Earnings Yield depends on market price.
A stored historical ranking may have been created under different local
timing assumptions.

For the strict backtest, the financial statement analysis date can
remain fixed while `market_price_date` is set separately to the common
session.

This allows the cohort to be compared using the same market-information
boundary.

## Purchase and Exit Prices

Valuation/reranking uses the appropriate raw market price required by
the analytical formula.

Return measurement uses `adjusted_close` so that splits and dividends
are represented by the source’s adjusted-price series.

Raw close is never substituted for a missing adjusted close when
calculating total return.

A security without a qualifying adjusted purchase or exit value is
excluded from the relevant return result rather than silently switching
methodologies.

## Backtest Stages

The strict workflow is conceptually:

1.  Select a historical Magic Formula quarter.
2.  Load the source ranking cohort.
3.  Resolve required SEC statement matches.
4.  Validate ticker/CIK identity for the historical period.
5.  Exclude unresolved or insufficiently supported securities.
6.  Determine a common information cutoff.
7.  Select the next common trading session.
8.  Rerank the surviving cohort using the common market-price date.
9.  Select the requested top-N positions.
10. Obtain adjusted purchase and exit values.
11. Calculate position returns.
12. Calculate equal-weighted cohort/period summaries.
13. Report exclusions and data-quality conditions.

## Exclusion Policy

The backtest is designed to expose why securities leave the cohort.

Possible exclusions include:

- missing required SEC statement matches;
- low-confidence filing matches;
- unresolved or ambiguous ticker/CIK history;
- missing common-session market data;
- missing adjusted purchase price;
- missing adjusted exit price; or
- other explicit data-quality failures.

Missing data should reduce the usable cohort rather than be replaced
with incompatible data.

## Outputs

A backtest may produce:

- original cohort size;
- qualified/reranked cohort size;
- exclusion counts and reasons;
- common information cutoff;
- purchase date;
- exit date;
- selected top-N securities;
- per-position adjusted returns;
- equal-weighted mean return;
- median return; and
- supporting ranking/selection metadata.

Outlier-sensitive summary statistics should be interpreted carefully.

## Current Validation Status

The project has successfully run an availability-aware pilot for the
2025-03-31 Magic Formula quarter.

That pilot demonstrated the end-to-end mechanics of:

- SEC-qualified statement timing;
- explicit exclusions;
- common-session reranking;
- adjusted purchase/exit prices; and
- equal-weighted return calculation.

The observed period result was heavily influenced by a single
extreme-return position. The pilot therefore validates pipeline behavior
rather than establishing strategy efficacy.

Exact cohort counts and historical local-database coverage are
operational state and may change as source data is refreshed; they
should not be treated as permanent architecture documentation.

## Known Limitations

### Financial Values Are Not Accession-Pinned

SEC metadata controls when information is considered available, but the
normalized Alpha Vantage financial values are not tied to a specific SEC
accession.

Later restatements may therefore affect historical values.

### Survivorship Bias

The historical Magic Formula universe is derived from the project’s
available security universe and should not be assumed to represent a
complete contemporaneous investable universe for every historical date.

This can introduce survivorship bias.

### Historical Ticker / CIK Identity

Some predecessor relationships and historical ticker/CIK intervals
remain unresolved.

Strict workflows exclude unsupported identities, but broader historical
completeness requires additional research.

### Adjusted-Price Coverage

Some securities may lack complete adjusted-price histories from the
source provider.

The project preserves these gaps explicitly and does not replace them
with raw close for total-return calculations.

### Strategy Interpretation

A successful historical period does not demonstrate future performance.

The current backtest should be treated as an engineering and research
tool for testing methodology, data integrity, and historical
assumptions.

## Running the Workflow

The repository provides installed CLI commands for preparing data and
running Magic Formula backtests.

Typical preparation includes:

``` bash
investment-prepare-backtest initialize --execute
investment-prepare-backtest import-sec --execute
investment-prepare-backtest match --execute
investment-prepare-backtest status
```

Adjusted-price data can be refreshed through the normal updater or
dedicated backfill workflow.

Example backtest:

``` bash
investment-backtest-magic-formula --quarter-date 2024-03-31 --top 30
```

Review-only modes should be used where available before executing
workflows that modify local state.

## Research Boundary

Backtesting is not on the critical path for Reveal v1.0 beyond
maintaining a working, documented implementation.

Additional strategy optimization, machine-learning weighting, and broad
historical efficacy research belong in future research work unless they
directly support a defined product requirement.

## Related Documentation

- `SEC_POINT_IN_TIME.md` — SEC availability and historical identity
  rules.
- `DATA_PIPELINE.md` — ingestion, persistence, adjusted-price behavior,
  and data-access boundaries.
