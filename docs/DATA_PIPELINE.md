# Data Pipeline

## Purpose

This document describes how Reveal moves external financial and market
data from source systems into local persistence and then exposes that
data to the analytical and application layers.

The pipeline is designed around three principles:

1.  preserve source meaning rather than silently manufacturing missing
    values;
2.  keep persistence and data access separate from analytical
    calculations; and
3.  make update, date-selection, and data-quality behavior explicit
    enough to reproduce and test.

This document describes the technical pipeline. Product interpretation
belongs in the application and selection-policy specifications.

## Pipeline Overview

``` text
External Sources
      |
      +-- Alpha Vantage
      +-- SEC Bulk Metadata / Identifier Data
              |
              v
        data_ingestion/
              |
              v
       Local Source Data
              |
              v
        Securities_DB/
        SQLite Persistence
              |
              v
         data_access/
              |
              v
          analytics/
              |
              v
          mvp/service
              |
              v
   SecurityAnalysisResult
              |
              v
        Presentation
```

## External Sources

### Alpha Vantage

Alpha Vantage supplies the project’s primary company financial and
market datasets, including financial statements, company information,
and daily adjusted price data.

Daily adjusted data can contain:

- raw open, high, low, close, and volume;
- adjusted close;
- dividend amount; and
- split coefficient.

Alpha Vantage API credentials are supplied through the
`ALPHAVANTAGE_API_KEY` environment variable and must not be committed.
An API key is required only for live Alpha Vantage ingestion and refresh
operations; it is not required to analyze an installed starter database.

### SEC Data

SEC datasets are used for:

- ticker/CIK identifier mapping;
- filing form and report dates;
- filing and acceptance timestamps;
- accession numbers; and
- point-in-time statement availability.

The project imports filing metadata from a local SEC bulk submissions
archive rather than requiring a live SEC request during analysis or
backtest execution.

## Ingestion Layer

`data_ingestion/` owns retrieval and discovery behavior.

Its responsibilities include:

- requesting supported source data;
- discovering or resolving securities;
- writing downloaded source datasets to the expected local structure;
  and
- leaving analytical interpretation to downstream layers.

Ingestion should not contain investment-selection policy.

## Persistence Layer

`Securities_DB/` owns SQLite persistence and schema-related behavior.

Primary persistence concerns include:

- normalized company financial data;
- OHLCV market data;
- Magic Formula ranking results;
- SEC filing metadata;
- ticker/CIK identity intervals;
- statement-to-filing matches; and
- maintenance/backfill state where applicable.

Persistence code should store source and derived database artifacts
without becoming the application’s presentation layer.

`Securities_DB/package_databases.py` exports an explicitly selected, compact
starter archive from existing SQLite data. It carries the needed source tables,
SEC match metadata, and the rank-only Magic Formula database for those tickers.
The install command verifies the archive and fills an empty data root before
the application starts. Full local databases remain outside Git; the starter
archive is added to a release only after its contents and rights are reviewed.

## OHLCV Data

The `ohlcv_daily` data model stores raw market values and may also
contain:

- `adjusted_close`;
- `dividend_amount`;
- `split_coefficient`;
- `price_source`; and
- `loaded_at_utc`.

Existing raw rows remain usable while adjusted fields are populated.

An unavailable adjusted value remains `NULL`. Historical total-return
workflows must not silently substitute raw close for a missing adjusted
close.

## Data Access Layer

`data_access/` is the boundary between persisted data and analytical
code.

It provides access to:

- balance sheets;
- cash-flow statements;
- income statements;
- earnings reports;
- company details;
- OHLCV price history; and
- SEC filing metadata.

Shared date-selection rules are centralized rather than independently
reimplemented by each analytical module.

### Statement Selection

When prior history exists, annual and quarterly statement selection uses
the latest applicable fiscal period on or before the requested
information boundary.

Strict historical workflows must not use compatibility behavior that
would select a statement from after the simulated information date.

### Price Selection

Price lookup uses the latest trading session on or before the requested
market-price date where that behavior is appropriate.

A future market price must not be substituted merely because an earlier
price is unavailable.

Backtesting may impose stricter common-session rules described in
`BACKTESTING.md`.

## Analytics Layer

`analytics/` consumes data through the access layer and owns financial
calculations and analytical methods.

Examples include:

- financial assessment;
- Graham-style calculated values and criteria;
- Magic Formula Return on Capital and Earnings Yield;
- market-price and volatility analytics; and
- historical backtesting.

Analytics should not depend on dashboard-specific presentation behavior.

## Application Service Boundary

`mvp/service.py` maps analytical results into the stable
`SecurityAnalysisResult` application contract defined in
`mvp/models.py`.

This boundary exists so that presentation code can consume a coherent
application result without:

- querying database tables directly;
- recreating analytical formulas;
- knowing how individual source files are stored; or
- silently changing missing-data behavior.

Partial analysis is allowed when documented eligibility or history
requirements prevent an analytical section from being completed. Those
conditions are exposed through calculation warnings rather than hidden.

## Update Workflow

The recurring security updater refreshes supported local security data
through the normal ingestion and persistence path.

The updater is also used for targeted adjusted-price refreshes. A
security may require an OHLCV update when its latest raw price is
current but adjusted fields remain incomplete.

For large adjusted-price batches, the dedicated backfill workflow is
resumable and records run/event state.

## Data Quality Rules

The pipeline should distinguish among:

- source data that is present;
- data that is legitimately zero;
- explicit `NULL` values;
- unavailable source data;
- values that cannot be calculated;
- unresolved security identity; and
- excluded historical observations.

These states should not be collapsed into a default numeric value merely
to keep a calculation running.

## Reproducibility

The project provides:

- documented installation and environment setup;
- pinned/constrained runtime dependencies;
- automated tests;
- documented environment-variable configuration;
- CLI entry points for operational workflows; and
- review-only modes for destructive or expensive operations where
  implemented.

Operational commands should be safe to inspect before execution whenever
the workflow can materially modify local data.

## Boundaries

The data pipeline does **not** determine whether a security is a good
investment.

Its responsibility is to make reliable, traceable data available to the
analytical layer. Financial interpretation belongs in the analytical and
product-policy layers.

## Related Documentation

- `SEC_POINT_IN_TIME.md` — filing availability, statement matching,
  identity, and historical information boundaries.
- `BACKTESTING.md` — historical cohort construction and return
  measurement.
- `../scripts/APPLICATION_PRODUCT_SPEC.md` — product purpose and user-facing
  behavior.
- `../scripts/SELECTION_POLICY.md` — analytical and eligibility policy.
