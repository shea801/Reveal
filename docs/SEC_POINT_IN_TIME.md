# SEC Point-in-Time Data

## Purpose

This document describes Reveal’s SEC metadata layer and the rules used
to determine whether a financial statement was publicly available at a
historical analysis date.

The purpose of this layer is to reduce look-ahead bias in historical
analysis by separating:

- a financial statement’s fiscal period;
- the date the filing was submitted;
- the filing acceptance timestamp;
- the filing accession identity; and
- the historical relationship between a ticker and CIK.

The SEC layer controls information timing. It does not currently make
the normalized Alpha Vantage financial values accession-specific.

## Why Fiscal Period Alone Is Not Enough

A financial statement for a quarter or fiscal year was not necessarily
available to an investor on the statement’s period-end date.

For a historical analysis, Reveal therefore cannot treat:

``` text
fiscal period end == information availability date
```

as true.

A point-in-time workflow must determine when the corresponding filing
became publicly available and prevent the simulated analysis from using
it before that point.

## Source Data

Reveal imports relevant filing metadata from a local SEC bulk
submissions archive.

Relevant periodic filing forms include:

- 10-K;
- 10-Q;
- 20-F;
- 40-F; and
- selected 6-K filings where the matching method supports their use.

The normalized metadata retains report dates, filing dates, acceptance
timestamps, forms, and accession numbers.

## Normalized SEC Tables

### `sec_filing_metadata`

Stores one row per CIK/accession.

Ticker is deliberately not treated as filing identity. The SEC filing is
identified by CIK and accession number.

### `sec_ticker_cik_identity`

Stores explicit current or researched historical ticker/CIK identity
intervals.

This separation matters because ticker symbols can change, be reused, or
map differently through corporate history.

A current ticker-to-CIK mapping must not automatically be assumed to
have been historically valid.

### `sec_statement_matches`

Links locally stored annual or quarterly fiscal periods to candidate SEC
filings.

Each match retains information such as:

- filing/accession identity;
- match method;
- confidence; and
- ticker/CIK identity status.

Ambiguity remains visible to downstream historical workflows.

## Statement Matching

The matching process attempts to associate a locally stored financial
period with the filing that made that information public.

Strict historical analysis accepts only matches that satisfy the
project’s required confidence and identity rules.

The current strict backtesting policy accepts high- or medium-confidence
statement matches with confirmed identity history.

Low-confidence or unresolved matches are excluded rather than silently
accepted.

Low-confidence 6-K inference is not used by strict backtests.

## Information Cutoff

Historical cohort construction uses a common information cutoff.

Conceptually:

``` text
financial period
      |
      v
matched SEC filing
      |
      v
acceptance timestamp
      |
      v
information becomes eligible
```

A security cannot use a required statement in a strict historical cohort
until that statement’s qualifying filing is available.

`Securities_DB/availability_dates.py` exposes
`quarterly_financial_availability()` for this normalization. It requires one
annual and four quarterly SEC statement matches, high or medium confidence,
confirmed ticker/CIK identity, and valid timezone-aware acceptance timestamps.
It returns both the latest required UTC acceptance timestamp and its UTC date.
Fiscal period ends and Alpha Vantage `reportedDate` never substitute for a
missing qualified filing. A daily backtest starts looking for a trading session
strictly after the information cutoff.

When a cohort contains many securities, the workflow determines a shared
cutoff that satisfies the required information-availability rules and
then uses a common market session for valuation/reranking.

## Fiscal-Year-End Handling

An issuer normally does not file a separate fourth-quarter 10-Q.

For fiscal-year-end quarterly source rows, the corresponding annual
filing availability — such as a 10-K, 20-F, or 40-F — is used where the
matching logic identifies it as the relevant source.

## Ticker / CIK Identity

Ticker identity is treated separately from filing identity.

This avoids an unsafe assumption:

``` text
current ticker -> current CIK
therefore
same ticker -> same CIK at every historical date
```

Historical analysis excludes relationships that predate a confirmed
identity interval unless a researched historical interval establishes
the relationship.

Unresolved or ambiguous identity is a data-quality condition, not
something to guess around.

## Confidence and Exclusions

Strict historical workflows may exclude a security for reasons
including:

- no required statement match;
- low-confidence statement match;
- unresolved ticker/CIK identity;
- ambiguous historical identity; or
- insufficient source metadata.

Exclusion is preferable to manufacturing certainty.

The backtest output should make these exclusions visible so that cohort
size and data loss can be evaluated.

## Known Limitation: Financial Values Are Not Accession-Pinned

The SEC metadata layer establishes when a filing became available, but
the normalized financial values used by the project originate from Alpha
Vantage and are not currently stored by SEC accession.

Therefore, later restatements or source normalization changes may affect
a historical value even when the availability timestamp is historically
correct.

The project should describe the resulting analysis as
**availability-aware** rather than claiming perfect historical
reconstruction.

A fully accession-pinned financial dataset would require a different
source-data architecture.

## Known Limitation: Historical Identity Coverage

Not every historical ticker/CIK relationship has been researched or
modeled.

Current mappings are useful for present identity, but strict historical
workflows require explicit support before assuming older relationships.

This limitation is especially relevant to:

- ticker changes;
- mergers and reorganizations;
- predecessor entities;
- reused symbols; and
- securities whose current CIK relationship does not cover the requested
  historical period.

## Design Principle

Point-in-time analysis should prefer an explicit exclusion over an
apparently complete result built from information that may not have been
available.

The goal is not to maximize cohort size. The goal is to make the
historical information boundary inspectable and defensible.

## Related Documentation

- `DATA_PIPELINE.md` — source ingestion, persistence, data access, and
  data-quality behavior.
- `BACKTESTING.md` — use of filing availability in historical Magic
  Formula cohorts.
