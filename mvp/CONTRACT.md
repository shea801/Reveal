# Reveal Application Output Contract

`mvp/models.py` defines the principal `SecurityAnalysisResult` model and
companion results for eligibility, ranked selection, peer distribution,
cohort membership, and annual selected/peer history. `mvp/service.py`
builds these results and contract-shaped dictionaries.
`mvp/CONTRACT.md` defines what the Reveal application output means.

## Status

Version: 0.6.3 - Reveal availability-aware historical comparison.

Status: frozen for the Reveal v1 baseline unless a test-backed change updates
this file. Dashboard and export work should treat this contract as the source
of truth.

## Purpose

The Reveal application output represents a repeatable value-investment analysis
snapshot for a single common stock on an `analysis_date`. It combines identity
fields, current valuation context, financial quality metrics, Graham Defensive
criteria, Graham Enterprising criteria, Magic Formula-style metrics, and
data-quality metadata.

The output is educational/research-oriented and is not financial advice.

## Entry Points

- Python model: `mvp.models.SecurityAnalysisResult`
- Peer-distribution model: `mvp.models.FinancialMetricDistribution`
- Historical-comparison models: `mvp.models.HistoricalMetricObservation` and
  `mvp.models.HistoricalMetricComparison`
- Comparable-security models: `mvp.models.ComparableSecurity` and
  `mvp.models.ComparableSecurityCohort`
- Eligibility model: `mvp.models.SecurityEligibilityAssessment`
- Ranked-selector model: `mvp.models.MagicFormulaRankedSecurity`
- Security identifier search and resolution:
  `mvp.service.search_security_identifiers(query)` and
  `mvp.service.resolve_security_identifier(identifier)`
- Current ranked-selector builder:
  `mvp.service.current_magic_formula_ranked_securities()`
- Eligibility preflight:
  `mvp.service.assess_security_eligibility(ticker)`
- Python builder: `mvp.service.analyze_security(ticker, analysis_date=None)`
- Peer context builder:
  `mvp.service.financial_profile_distributions(result)`
- Comparable-security membership builder:
  `mvp.service.comparable_security_cohort(result, comparison_basis=None)`
- Contract dictionary helper:
  `mvp.service.eligible_common_stock_analysis(ticker=None, analysis_date=None, investor_type=None)`
- CLI entry point: `python3 scripts/analyze_security.py TICKER`

The dashboard resolves its text input against persisted SEC ticker, title,
and CIK metadata before eligibility and analysis. Ambiguous company names or
CIKs require the user to choose a ticker. The separate Magic Formula selector
uses the latest quarter in the persisted ranking database at dashboard startup.
Each `MagicFormulaRankedSecurity` contains `rank`, `ticker`, `company_name`, and
`quarter_date`, ordered by ascending rank. Company names come from stored
company details, with SEC ticker titles as a fallback. Selecting an option
fills the security input; analysis still requires the explicit Analyze action.
The selector is disabled when rankings are unavailable. Its quarter is
independent of the requested single-security `analysis_date` and does not
replace the point-in-time Magic Formula fields on `SecurityAnalysisResult`.

## Output Formats

JSON is the primary application output format. Dates are ISO strings in JSON and
contract dictionaries.

Text output is a human-readable summary for the CLI and may omit fields.

CSV export is deferred. When added, CSV columns should match the field order in
this contract.

## Eligibility Preflight

Interactive entry points evaluate eligibility before running the analytical
service. Reveal v1 accepts a common stock listed on a supported major U.S.
exchange when local data reports at least $250 million in market capitalization
and five years of annual financial and market-price history. Ineligible results
retain the security identity and every failed requirement so the presentation
layer can explain the decision without calling the analytics pipeline.

## Required Identity Fields

These fields are required for `data_complete=True`.

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `ticker` | string | no | Uppercase trading symbol. |
| `company_name` | string | no | Company or fund name available from local data. |
| `analysis_date` | date/string | no | Date used to select analysis inputs. JSON uses `YYYY-MM-DD`. |

## General Context Fields

| Field | Type | Nullable | Meaning                                                  |
| --- | --- | --- |----------------------------------------------------------|
| `company_description` | string | yes | Stored company description when available; its absence does not make the result incomplete. |
| `annual_financial_statement_analysis_date` | string | yes | date of annual financial statement used for analysis.    |
| `quarter_financial_statement_analysis_date` | string | yes | date of quarterly financial statement used for analysis. |
| `market_cap` | number | yes | Market capitalization from local data.                   |
| `market_cap_group` | string | yes | Local market-cap grouping used for comparisons.          |
| `sector` | string | yes | Sector classification.                                   |
| `industry` | string | yes | Industry classification.                                 |
| `total_sales_services` | number | yes | Revenue/sales value used by financial assessment.        |
| `price_to_earnings` | number | yes | Price divided by earnings per share when available.      |

## Market Price 

| Field               | Type   | Nullable | Meaning                                                  |
|---------------------|--------| --- |----------------------------------------------------------|
| `price_date`        | string | yes | Date of share price used for analysis.                   |
| `market_price_for_period` | number | yes | Share price selected for the analysis period.            |
| `min_200_day_price` | number | yes | Lowest price in the last 200 days.                       |
| `max_200_day_price` | number | yes | Highest price in the last 200 days.                      |
| `avg_price_200_day` | number | yes | Average price in the last 200 days.                      |
| `median_price_200_day` | number | yes | Median price in the last 200 days.                    |

## Core Valuation Fields

| Field | Type | Nullable | Formula / Meaning |
| --- | --- | --- | --- |
| `eps` | number | yes | Earnings per share for the selected period. |
| `eps_ttm` | number | yes | Sum of reported EPS for the latest four fiscal quarters on or before the analysis date. |
| `net_income_ttm` | number | yes | Sum of net income for the latest four fiscal quarters on or before the analysis date. |
| `ebit_ttm` | number | yes | Sum of EBIT for the latest four fiscal quarters on or before the analysis date. |
| `period_three_year_average_eps` | number | yes | Average EPS for the current three-year period. |
| `tangible_book_value_per_share` | number | yes | Tangible book value per share. |
| `graham_number` | number | yes | Graham Number from Defensive value logic. |
| `serenity_number` | number | yes | Enterprising valuation number from project logic. |
| `defensive_margin_of_safety` | number | yes | `graham_number / market_price_for_period`. |
| `enterprising_margin_of_safety` | number | yes | `serenity_number / market_price_for_period`. |

## Financial Strength Fields

| Field                                                       | Type   | Nullable | Meaning                                                                     |
|-------------------------------------------------------------|--------| --- |-----------------------------------------------------------------------------|
| `debt_to_equity`                                            | number | yes | Despite the legacy field name, total liabilities divided by annual equity (assets less liabilities); displayed as Liabilities to Equity. |
| `debt_to_assets`                                            | number | yes | Latest annual interest-bearing debt divided by total assets.                 |
| `longterm_debt_to_cash`                                     | number | yes | Annual long-term debt divided by cash and equivalents plus annual operating cash flow less capital expenditures. |
| `interest_coverage`                                         | number | yes | Operating/earnings coverage of interest expense.                            |
| `net_debt_to_free_cash_flow`                                | number | yes | Interest-bearing debt less cash and short-term investments, divided by positive annual free cash flow. |

## Profitability And Efficiency Fields

| Field                        | Type | Nullable | Meaning                                   |
|------------------------------| --- | --- |-------------------------------------------|
| `gross_margin`               | number | yes | Gross margin from financial assessment.   |
| `free_cash_flow`             | number | yes | Annual operating cash flow less capital expenditures. |
| `free_cash_flow_margin`      | number | yes | Annual free cash flow divided by annual revenue. |
| `estimated_owner_earnings`  | number | yes | Current source-supported owner-earnings proxy: annual operating cash flow less capital expenditures. |
| `estimated_owner_earnings_yield` | number | yes | Estimated owner earnings divided by point-in-time market capitalization. |
| `operating_income`           | number | yes | Operating income for the selected period. |
| `inventory_turnover`         | number | yes | Inventory turnover ratio.                 |
| `return_on_assets`           | number | yes | Net income divided by assets.             |
| `return_on_equity`           | number | yes | Net income divided by equity.             |
| `return_on_invested_capital` | number | yes | Annual NOPAT divided by average annual invested capital. |
| `financial_profile_return_on_capital` | number | yes | Annual EBIT divided by average annual capital employed. |
| `eps_cagr_5yr`              | number | yes | EPS CAGR from five aligned annual observations with positive endpoints and four compounding intervals. |

`eps_cagr_5yr` is retained as the established model/JSON contract field name.
Its `5yr` suffix refers to the five required annual EPS observations, not five
elapsed growth years. Those observations span four compounding intervals, so
the user-facing label is **EPS CAGR (4-Year Growth)**. The field name,
calculation, and service mapping remain unchanged.

`financial_profile_return_on_capital` and Magic Formula
`return_on_capital` are intentionally different. Financial Profile ROC is a
descriptive annual metric: EBIT divided by average capital employed, where
capital employed is total assets less current liabilities. Magic Formula ROC
uses TTM EBIT and the project-defined quarter-aware Magic Formula capital base
for ordinal ranking. They answer different analytical questions and must be
labeled separately whenever both are shown.

## Financial Profile Distribution Contract

`FinancialMetricDistribution` is a companion application result. The service
defaults to the seven frozen Financial Profile fields; the dashboard requests
those plus ten additional descriptive overview fields for current
cross-sectional context. It does not change the value stored in
`SecurityAnalysisResult` and does not create a Reveal score or ranking.

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `metric` | string | no | Descriptive field represented by the distribution. |
| `comparison_basis` | string | no | Cohort tier used, such as `Industry + market cap`. |
| `comparison_group` | string | no | User-readable cohort name. |
| `sample_size` | integer | no | Finite metric observations included in the distribution. |
| `candidate_count` | integer | no | Eligible cohort members considered before missing metric values were removed. |
| `values` | tuple/list of numbers | no | Sorted finite observations used by dashboard charts. |
| `selected_value` | number | yes | Selected security's unchanged metric value. |
| `percentile` | number | yes | Low-to-high percentile position within the observed values. |
| `p10`, `p25`, `median`, `mean`, `p75`, `p90` | number | no | Robust spread and center statistics for the selected cohort. |

The current implementation provides cross-sectional metric values at the
requested analysis cutoff using the latest locally stored company classification
and eligibility metadata for cohort membership. It is not a strict historical
universe. For each metric, the service selects the first cohort with at least
five finite observations using this order:

1. same industry and market-cap group;
2. same industry;
3. same sector and market-cap group;
4. same sector; and
5. the eligible U.S. common-stock universe.

Peer metric values come from `FinancialAssessment.to_dict()`, the canonical
point-in-time metric source. Missing and non-finite values are excluded and are
visible through the difference between `candidate_count` and `sample_size`.
The selected security's unavailable value remains `None`; a peer spread may
still be displayed without assigning that security a percentile.

Percentile reports numeric position from low to high. It is not an investment
quality rank. The dashboard must state each metric's usual direction and
important caveat without converting peer position into a recommendation.
The Descriptive Annual Metrics table presents the same companion result as a compact
percentile axis with ticks at 0, 10, 25, 50 (median), 75, 90, and 100. The
selected-security marker uses `percentile`; endpoint tick values use the first
and last sorted observations. This is a presentation of existing contract data,
not an additional metric or score.
Historical cohort percentile distributions remain deferred. Aligned annual
metric histories for the selected security and one peer are governed by the
Historical Financial Profile Comparison Contract below.

## Comparable-Security Cohort Contract

`ComparableSecurityCohort` exposes the membership behind the current peer
cohort system without calculating financial metrics for every member. It uses
persisted `company_details` metadata through `CompanyDetails.get_peer_metadata()`
and does not call `analyze_security()` or `FinancialAssessment`.

`ComparableSecurity` fields:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `ticker` | string | no | Normalized ticker symbol for the cohort member. |
| `company_name` | string | no | Persisted company name. |
| `industry` | string | yes | Current locally stored industry classification. |
| `sector` | string | yes | Current locally stored sector classification. |
| `market_cap_group` | string | yes | Market-cap classification derived from current persisted market capitalization. |

`ComparableSecurityCohort` fields:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `selected_ticker` | string | no | Security for which comparison membership was requested. |
| `comparison_basis` | string | no | Canonical cohort tier name. |
| `comparison_group` | string | no | User-readable cohort label. |
| `members` | tuple/list of `ComparableSecurity` | no | Ticker-sorted eligible cohort membership, including the selected security. |

When `comparison_basis` is omitted, the service returns the narrowest current
metadata cohort containing at least five eligible members, falling back through
the documented hierarchy. A caller can pass a `FinancialMetricDistribution`
object's `comparison_basis` to retrieve the exact candidate membership behind
that metric's selected distribution. Supported tiers remain Industry + market
cap, Industry, Sector + market cap, Sector, and Eligible market.

Membership applies the same current common-stock, supported-exchange, minimum
market-cap, and unsupported-name filters as the distribution service. It does
not assert that every member has a usable value for a particular metric; that
difference remains visible through the distribution's `candidate_count` and
`sample_size`. Classification and market-cap membership use the latest locally
stored metadata and are not a strict historical-universe representation.

## Graham Screening Fields

These fields may be `None` when the ticker lacks enough history or source data.
Skipped sections must be recorded in `calculation_warnings`.

The Defensive working-capital tests apply to Industrial and Financial sectors.
The Utility debt-to-book-equity test applies to Utilities. Sector-specific
criteria outside their documented sector are listed in
`not_applicable_fields` and do not cause the Defensive summary to fail or
become unavailable.

| Field                                                      | Type   | Nullable | Meaning                                                                                |
|------------------------------------------------------------|--------| --- |----------------------------------------------------------------------------------------|
| `defensive_revenue_requirement_met`                        | bool   | yes | Defensive: annual revenue is at least $500 million, or $250 million for Utilities.     |
| `current_assets_200pct_or_greater_current_liabilities_met` | bool   | yes | Defensive: current-assets gte 200% of current-liabilities                              |
| `current_assets_to_current_liabilities_ratio`              | number | yes | Defensive: current-assets to current-liabilities ratio value.                          |
| `current_assets_150pct_or_greater_long_term_debt_met`      | bool   | yes | Enterprising: current-assets/net-current-assets gte 150% of long-term-debt.            |
| `current_assets_150pct_or_greater_than_long_term_debt_ratio` | number | yes | Enterprising: (current-assets/net-current-assets) /long-term-debt ratio.             |
| `long_term_debt_less_than_net_current_assets_met`          | bool   | yes | Defensive: longterm debt less than net current assets.                                 |
| `long_term_debt_to_net_current_assets_ratio`               | number | yes | Defensive and Enterprising: long-term debt divided by net current assets.              |
| `utility_debt_to_book_equity_met`                          | bool   | yes | Defensive Utility test: long-term debt is no greater than 2x book equity.              |
| `long_term_debt_to_book_equity_ratio`                      | number | yes | Utility long-term debt divided by book equity.                                          |
| `long_term_debt_110pct_or_less_to_net_current_assets_met`  | bool   | yes | Enterprising: long-term-debt lte 110% of net-current-assets.                           |
| `positive_earnings_for_the_past_10_years_met`              | bool   | yes | Defensive: positive earnings over the ten-year lookback.                               |
| `eps_3yr_average_33pct_gte_10yr_previous_eps_met`          | bool   | yes | Defensive: current 3yr EPS average gte 133% of the 10-year-lookback 3yr EPS average.   |
| `eps_3yr_average_to_10yr_previous_eps_ratio`               | number | yes | Defensive: current 3yr EPS average divided by the 10-year-lookback 3yr EPS average.    |
| `continuous_dividend_payments_for_past_20yrs_met`          | bool   | yes | Defensive: adjusted market history shows a common-stock dividend in every fully covered fiscal year of the 20-year window. |
| `average_dividend_payments_for_past_20yrs`                 | number | yes | Defensive: average reported common-stock dividend payment over the past 20 annual statements. |
| `price_15x_or_less_eps_3yr_average_met`                    | bool   | yes | Defensive: price is lte 15x the current 3-year EPS average.                            |
| `price_to_eps_3yr_average`                                 | number | yes | Defensive: price divided by the current 3-year EPS average.                            |
| `price_150pct_or_less_book_value_met`                      | bool   | yes | Defensive: Price to book value should be lte 150% (1.5x).                              |
| `price_to_book_value`                                      | number | yes | Defensive: Price / BV                                                                  |
| `no_earnings_deficit_for_5yrs_met`                         | bool   | yes | Enterprising: no negative earnings (netIncome) each year over a 5 year lookback.       |
| `earnings_growth_greater_than_5yrs_previous_met`           | bool   | yes | Enterprising: current earnings (netIncome) greater than earnings from 5 year lookback. |
| `earnings_to_5yr_earnings_lookback_ratio`                  | number | yes | Enterprising: current net income divided by its 5-year-lookback value.                 |
| `price_120pct_or_less_tangible_book_met`                   | bool   | yes | Enterprising: price is lte 120% of tangible book value.                                |
| `price_to_tangible_book_value`                             | number | yes | Enterprising: current price / TBV.                                                     |
| `defensive_criteria_met`                                   | bool   | yes | True only when every available Defensive criterion was evaluated and passed.           |
| `enterprising_criteria_met`                                | bool   | yes | True only when every available Enterprising criterion was evaluated and passed.        |

The contract dictionary helper also retains compatibility aliases for evaluated
boolean checks prefixed with `defensive_criteria_` or
`enterprising_criteria_`. These aliases are omitted when the corresponding
criterion was not evaluated.

## Magic Formula Fields

| Field | Type | Nullable | Formula / Meaning                                                                  |
| --- | --- | --- |------------------------------------------------------------------------------------|
| `return_on_capital` | number | yes | TTM EBIT divided by the project-defined capital base from the latest available quarterly balance sheet. |
| `earnings_yield` | number | yes | TTM EBIT divided by the project-defined enterprise value proxy. |
| `magic_formula_quarter_date` | string | yes | Latest persisted ranking quarter on or before `analysis_date`. |
| `magic_formula_associated_annual_date` | string | yes | Annual fiscal period used for non-TTM ranking inputs. |
| `magic_formula_financial_statement_availability_date` | string | yes | Latest `reportedDate` needed for the quarter's TTM and annual inputs; a report-availability proxy rather than an SEC filing timestamp. |
| `return_on_capital_rank` | integer | yes | Ordinal ROC rank within the eligible quarterly cohort, highest ROC first. |
| `earnings_yield_rank` | integer | yes | Ordinal Earnings Yield rank within the eligible quarterly cohort, highest yield first. |
| `total_roc_ey_score` | integer | yes | Sum of `return_on_capital_rank` and `earnings_yield_rank`; lower is better. |
| `magic_formula_rank` | integer | yes | Overall ordinal quarter rank after sorting `total_roc_ey_score` ascending. |

## Data Quality Fields

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `data_complete` | bool | no | True only when required identity fields exist and no warnings were recorded. |
| `missing_fields` | tuple/list of strings | no | Required identity fields that were missing or blank. |
| `calculation_warnings` | tuple/list of strings | no | Analysis sections skipped or ticker-level analysis errors. |
| `not_applicable_fields` | tuple/list of strings | no | Contract fields intentionally excluded for this security or methodology. |
| `field_explanations` | tuple/list of field/reason pairs | no | User-readable reasons for fields identified as not applicable. |

## Null, Missing, And Failed Criteria

- **Reported value:** A numeric amount explicitly reported by the source,
  including zero, is used according to the metric's documented calculation.
- **Database `NULL`:** No numeric amount is stored. The source may have omitted
  the item, considered it inapplicable, or lacked the data; `NULL` alone does
  not establish which explanation applies and does not mean zero.
- **Supported zero interpretation:** A specific calculation may use zero only
  when source evidence or its documented rule establishes that interpretation.
  Do not generalize that rule to other `NULL` fields.
- **Unavailable result:** A required input that cannot be established remains
  `None` in the application result; dependent calculations remain unavailable
  unless a documented alternative is supported. An intentional methodology
  exclusion is `Not applicable`, not an inferred zero or failed criterion.
- **Negative value:** A negative observation remains valid where the metric
  permits it. Negative free cash flow is not a Financial Profile ranking error;
  FCFM remains descriptive, while Net Debt / FCF is unavailable when annual
  free cash flow is zero or negative under its frozen rule.

`None` in an application result means a value was not available or was not
calculated from current source data. A database `NULL` means no numeric amount
is stored; neither state by itself establishes zero or a failed criterion.
A documented, source-supported rule is required before a particular missing
input can be interpreted as zero for a calculation.

`not_applicable_fields` distinguishes a deliberate methodology exclusion from
an unavailable value. The presentation layer must label those fields `Not
applicable` and use `field_explanations` to explain why. An applicable `None`
value is labeled `Unavailable`.

Boolean `False` means a criterion was evaluated and failed.

`data_complete=False` means the result should remain visible but should not be
treated as a fully comparable result without reading `missing_fields` and
`calculation_warnings`.

## Date Semantics

`analysis_date` is the requested information cutoff and remains the date passed
to the analysis workflow. When prior history exists, annual and quarterly
statement lookup uses the latest fiscal period on or before that date. TTM
calculations use the latest four complete quarterly periods on or before the
same cutoff.

The seven Financial Profile metrics use the latest completed common annual
period on or before the cutoff. ROIC and Financial Profile ROC also require the
preceding annual balance sheet for their average capital denominators. Five-year
EPS CAGR requires five annual EPS dates aligned with annual income-statement
dates and uses the four intervals between them. Missing source values remain
`None`; zero and negative values remain valid where the formula permits them.
Net debt/free cash flow is unavailable when free cash flow is zero or negative.

The Defensive 20-year dividend criterion uses adjusted daily market-history
dividend events, grouped into fiscal-year windows. A fully covered fiscal year
with no common-stock dividend is `False`; incomplete market-history coverage is
`None`, not a failed criterion. The displayed average dividend amount remains
the average reported common-stock payout from the annual cash-flow statements.

The quarterly investment workflow targets a price approximately one week after
the calendar quarter containing `analysis_date`. `OHLCVPriceData` resolves that
target to the latest trading session on or before the target date. This handles
weekends and market holidays without silently selecting a later price.

`FinancialAssessment.to_dict()` currently exposes additional date metadata:

- `price_date`: the actual trading date selected from OHLCV history;
- `annual_financial_statement_analysis_date`: the common annual fiscal-statement date used by the
  assessment (specific to the date period if a date is provided).
- `quarter_financial_statement_analysis_date`: the latest quarterly fiscal-statement date used by the
  assessment (specific to the date period if a date is provided).

`FinancialAssessment.to_dict()` now produces 200-day market price metrics:
`min_200_day_price`, `max_200_day_price`, `avg_price_200_day`, and
`median_price_200_day`. This data will be used to help evaluate market-price
risk and asset volatility.

Magic Formula ranking rows also retain the associated annual fiscal date and a
`financial_statement_availability_date` proxy derived from the latest required
quarterly earnings `reportedDate`. Future strict backtesting should prefer SEC
filing timestamps when those become available.

The statement selector currently retains a compatibility fallback to the
earliest available fiscal period when `analysis_date` predates all statement
history. Strict point-in-time backtests must reject that boundary result rather
than treating the future period as available.


## Historical Financial Profile Comparison Contract

`HistoricalMetricComparison` is the presentation-ready service result for one
Financial Profile metric across the selected security and, optionally, one
peer. It defines aligned annual history, period availability, and warning state
without requiring the dashboard to calculate dates or comparison eligibility.
It is not a historical cohort percentile distribution.

`HistoricalMetricObservation` fields:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `ticker` | string | no | Normalized ticker associated with the observation. |
| `anchor_fiscal_year` | integer | no | Selected security's fiscal year defining the displayed comparison position. |
| `fiscal_year` | integer | no | Observation's actual fiscal year, which may differ from the anchor year. |
| `annual_statement_date` | string | no | ISO annual fiscal-statement date supplying the metric. |
| `statement_availability_date` | string | no | ISO date on which the underlying annual filing became available. |
| `price_date` | string | yes | Actual market-price date used by a price-dependent metric. Required for historical EOEY and `None` for the other Financial Profile metrics. |
| `value` | number | no | Unchanged finite Financial Profile metric value. |

`HistoricalMetricComparison` fields:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `metric` | string | no | Financial Profile field represented by the comparison. |
| `analysis_date` | date | no | Information cutoff applied to every observation. |
| `requested_period` | integer or `all` | no | Period requested by the caller. |
| `applied_period` | integer | no | Actual number of annual periods rendered after alignment or fallback. |
| `available_periods` | tuple/list of integers or `all` | no | Period controls supported by the shorter comparable history, or by the selected security without a peer. |
| `selected_ticker` | string | no | Originally analyzed security. |
| `peer_ticker` | string | yes | Selected peer, or `None` for a single-security history. |
| `anchor_fiscal_years` | tuple/list of integers | no | Oldest-to-newest selected-security fiscal years defining the displayed positions. |
| `series` | tuple/list of `HistoricalMetricObservation` | no | Presentation-ready observations for the applied display window. |
| `limiting_tickers` | tuple/list of strings | no | Securities whose valid history shortens or prevents the requested comparison. |
| `max_fiscal_period_offset_days` | integer | no | Largest absolute difference between paired annual statement dates; zero without a peer. |
| `warning_codes` | tuple/list of strings | no | Machine-readable warning states: `limited_history`, `no_comparable_history`, and/or `fiscal_period_offset`. |

### V1 Annual-History Alignment Policy

`analysis_date` is the common information cutoff. For every requested ticker,
Reveal independently selects the latest contiguous annual Financial Profile
observations whose filings were available by that cutoff. The selected security
defines the displayed anchor periods. A peer's annual observations are paired
by recency order rather than by matching fiscal-year numbers: latest with
latest, second latest with second latest, and so forth.

For example, when the selected security's latest available annual statement
ends in June and the peer's latest available annual statement ends in December,
both latest observations occupy the selected security's latest anchor position.
Each observation retains its actual `fiscal_year`, `annual_statement_date`, and
`statement_availability_date`; the peer is not relabeled as though it shared the
selected security's fiscal calendar.

An observation is valid only when the selected metric is finite and persisted
SEC filing metadata shows that its annual statement was available by
`analysis_date`. Missing availability metadata makes the observation
unavailable for comparison. Reveal does not estimate filing dates, substitute
later statements, interpolate missing values, carry values forward, prorate
annual statements, or calendarize unlike fiscal years.

Historical EOEY uses the latest trading close on or before the annual filing's
`statement_availability_date` as its point-in-time market-price input. The
actual trading date selected by the price-access layer is retained in
`price_date`. Reveal does not substitute a price after the filing-availability
date. `price_date` is `None` for Financial Profile metrics that do not use a
market-price input.

The security with fewer contiguous valid annual observations determines the
maximum comparison length. `anchor_fiscal_years` contains the selected
security's fiscal years for the applied display window. `series` is ordered from
oldest to newest anchor period, with the selected security before the peer
within each anchor period. `limiting_tickers` identifies every security that
prevents the requested period from being displayed in full.

Available comparison-period labels are `1`, `3`, `5`, `7`, `10`, and `All`.
A numeric option is included in `available_periods` only when both securities
have at least that many contiguous valid observations. `all` represents the
complete comparable history allowed by the shorter series. Five years is the
default when available; otherwise the service applies the longest enabled
numeric period below five years. Without a peer, period availability is based
only on the selected security's contiguous valid annual history.

`warning_codes` contains `limited_history` when one or both securities prevent
the requested period from being displayed. If the peer has no valid annual
observation available by the cutoff, it contains `no_comparable_history` and
`series` contains only the selected security's available history.

Fiscal-period offsets are disclosed but do not invalidate an otherwise valid
comparison. The service records the largest paired statement-date difference
in `max_fiscal_period_offset_days` and adds `fiscal_period_offset` to
`warning_codes` when that difference exceeds 183 days. This warning is a
presentation and interpretation aid, not a pass/fail assessment. It does not
add a limiting-history asterisk unless the security also appears in
`limiting_tickers`.

This annual-history policy supports descriptive dashboard comparison. Strict
historical backtesting must apply the same availability rule separately at each
historical decision date and remains outside this comparison contract.


## Ranking Contract

Magic Formula ranking fields are persisted and exposed separately from raw
financial metrics. Each quarterly cohort assigns unique ordinal ROC and
Earnings Yield ranks from 1 through n, sums those ranks, then assigns a unique
overall rank from the lowest combined score to the highest. Ties use stable,
documented ticker-based ordering rather than duplicate rank numbers.

Required future comparison groups:

- all eligible common stocks
- same `market_cap_group`
- same `sector`
- same `industry`

Ranking fields should document direction explicitly. Higher-is-better and
lower-is-better metrics must not be mixed without a named scoring rule.

## Deferred Fields

- ETF-specific analytics fields
- Dashboard-only display labels
- CSV output
- Backtesting result fields
- Generalized availability-adjusted as-of dates outside the historical
  comparison and Magic Formula workflows
