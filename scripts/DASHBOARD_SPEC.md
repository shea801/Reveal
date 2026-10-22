Project: Reveal
Version: v0.6.3 availability-aware annual comparison
Start date: 9/23/2026
Current work date: 10/09/2026

This spec will be the authority on application presentation behavior.

`../mvp/CONTRACT.md` shall be the authority for the information supplied and displayed in the dashboard.

Refer to `../scripts/APPLICATION_PRODUCT_SPEC.md` for application scope, vision, and application parameters.
Refer to `../scripts/SELECTION_POLICY.md` for security selection criteria and process.


# DASHBOARD SPEC

This file will describe the dashboard design for the application.
This application lies within the 'Investment' project domain, and the current application working title is 'Reveal'
This file will define:
- Landing page
- Search
- Candidate lists
- Security detail view
- charts
- interactions


### CURRENT DEVELOPMENT STAGE
**2026-10-09**: Reveal v1 dashboard functionality is feature-frozen after
representative security, peer, and annual-history validation. Current
cross-sectional distributions cover seven frozen Financial Profile metrics
and ten additional descriptive overview fields; historical selected/one-peer
comparison covers the seven frozen metrics. CI, clean release verification,
public documentation/demo artifacts, and a release tag remain outstanding.
**2026-10-05**: Added ticker, SEC company-name, and CIK search with suggestions
from persisted SEC metadata. Added a searchable selector for the latest
persisted Magic Formula quarter, ordered by rank and showing rank, ticker, and
company name. Choosing a ranked security fills the Security field; Analyze
still starts the request. The Security Analysis overview now shows the stored
company description when available.
**2026-10-02**: Implemented the presentation-ready historical Financial Profile
comparison service and dashboard wiring. The analyzed security supplies the
displayed anchor periods, peer observations align by recency from the same
information cutoff, and actual statement, filing-availability, and historical
EOEY price dates remain visible. Dynamic period controls, limiting-history
asterisks, selected-only fallback, offset warnings, and the chart-only warning
border are active.
**2026-10-01**: Added an application-service contract that exposes the
securities belonging to any current comparison cohort from persisted company
metadata. Dashboard rendering of this list remains a separate presentation
step; retrieving membership does not run full analyses for cohort members.
**2026-09-28**: Replaced the Financial Profile table's descriptive-text column
with a compact one-dimensional peer-distribution spread. Each row shows fixed
percentile ticks at 0, 10, 25, median, 75, 90, and 100, plus a marker at the
selected company's percentile. Full descriptions and selectable charts remain
in the Peer Distribution section.
**2026-09-27**: Implemented the Financial Profile distribution matrix for
current peer comparison. Each metric uses the narrowest documented cohort with
at least five usable values and exposes cohort and sample-size provenance.
**2026-09-26**: The vertical slice implementation is complete and used to validate the data presented in the dashboard;
- bug fix found while validating dividend history now aligns the various data periods on specific dates and not dataframe index location;
- improved the syntax and created display information for ineligible securities and for failed analysis.
**2026-09-23**: The first single-page vertical slice is implemented in
`../dashboard`. It remains intentionally simple for rapid development and
testing and will be expanded in future iterations.


### CURRENT DASHBOARD WORKFLOW

User enters ticker / SEC company name / CIK, or selects a ranked ticker
      ↓
Dashboard resolves the identifier to a ticker
      ↓
mvp.service.assess_security_eligibility("TICKER_SYMBOL")
      ↓
Eligible? ── no ──> Ineligibility explanation
      │
     yes
      ↓
mvp.service.analyze_security("TICKER_SYMBOL")
      ↓
SecurityAnalysisResult
      ↓
Dashboard renders
      │
      ├── Security / Analysis Overview
      ├── Financial Profile
      ├── Peer Comparison and Distribution table + graph
      ├── Graham Analysis
      ├── Magic Formula
      └── Data Quality / Warnings


### PARAMETERS:

- Current cross-sectional peer context covers 17 descriptive metrics: seven
  frozen Financial Profile metrics plus ten current overview fields. Aligned
  selected-security/one-peer annual history covers the seven frozen metrics.
  Historical cohort percentile distributions remain deferred.


### INELIGIBLE SECURITIES

For securities that are ineligible for analysis as described in
`../scripts/SELECTION_POLICY.md` under "Eligible Securities":
- Provide an explanation of why the security is ineligible for analysis in this application.
  - Explanations should be concise and specific to the criteria that failed:
    - "'TICKER' is ineligible for analysis because 'TICKER' is a Warrant (or Preferred Stock, ETF, etc.), and not a Common Stock"
    - "'TICKER' is ineligible for analysis because it does not have enough financial data to complete analysis."
    - "'TICKER' is ineligible for analysis because 'TICKER' only has 3 years of financial data available, and a minimum of 5 is required for analysis."
    - "'TICKER' is ineligible for analysis because it does not meet the minimum market capitalization of $250 million US."
  - Following that explanation an explanation *why*:
  > "Reveal v1 requires an investment to be a common stock because the current analytical contract is designed for operating-company financial statements. Learn more about 'OTHER SECURITY TYPE' at the linked Investopedia overview."

#### Interpreting Criteria Conditions

In the case of a security where a pass/fail/unavailable tag or button is assigned:
- If a security has an 'unavailable' tag or button applied, further explanation needs to be given, for example:
  - Security doesn't have a long enough history for particular criteria in the 'Defensive' or 'Enterprising' Investor philosophies.
  - A security is not eligible for Magic Formula ranking because of its sector.
- For securities 'Defensive Investor' analysis, the following rules shall be applied:
  - As stated in `../scripts/SELECTION_POLICY.md` heading "Defensive Investor Criteria and as being defined within the application"
    - If a security is not a type of 'UTILITY', 'INDUSTRIAL', or 'FINANCIAL' company, then the criteria specific to those types shall not be applied and an explanation why.
      - A `Not applicable` tag is used instead of `Unavailable` when the criterion does not apply to a specific security.
  - Criteria that appears as 'unavailable' shall carry an explanation as to why the criteria is unavailable:
    - ex: when an intrinsic-value calculation cannot be completed with the
      available earnings input, its result is `Unavailable`; a negative input
      is not automatically missing or zero.
- If a metric does not apply to a particular security by nature of its type,
  sector, industry, or methodology, a `Not applicable` tag is used instead of
  `Unavailable`.
  - ex: if a security is a 'UTILITY' it won't qualify for a magic formula ranking, so it is 'not applicable'
    - that reason shall be explained to the user.

**Vocabulary**:
- Passed — criterion evaluated and passed.
- Failed — criterion evaluated and failed.
- Unavailable — criterion applies, but required data is unavailable.
- Not applicable — criterion intentionally does not apply to this security/methodology.

### Layout

##### INPUT:
The controls row contains a Security text input, optional analysis date,
Magic Formula ranking selector, and Analyze button, in that order at desktop
width. The controls wrap responsively at narrower widths.

1. The text input accepts a ticker, SEC-indexed company name, or CIK. Partial
   input shows suggestions from persisted `sec_tickers` records. Ambiguous
   names or CIKs require a ticker selection before analysis.
2. The searchable selector lists the latest persisted Magic Formula quarter in
   ascending rank order. Each option shows rank, ticker, and company name.
   Company names use persisted company details with SEC titles as fallback.
   Choosing an option fills the Security input; Analyze still runs the request.
   The selector is disabled if rankings cannot be loaded. Its quarter is fixed
   when the dashboard starts and is independent of the optional analysis date.

Dashboard layout is created using Plotly Dash and dash-bootstrap-components.
Header with the application title and version number.
"An investment application of practical counsel" to be written and centered under the header.

The current layout presents:

- an eligibility explanation before analysis when a security is outside the
  Reveal v1 universe;
- Security Analysis, Descriptive Annual Metrics, Peer Distribution/Metric
  History, criteria-based analysis, and calculation-context sections for
  eligible securities;
- The first `Security Analysis` section places ticker/name and company
  description in the heading, with sector, industry, and market-cap tags in a
  neighboring stack. A compact single-column key/value context list shows
  analysis date, market and company facts without repeating those tags or the
  description. Comparison-cohort details and membership are shown separately.
- `Descriptive Annual Metrics` has 17 scrollable rows, hover calculation
  details, and compact inline percentile spreads. A current cross-sectional
  summary sits alongside the table on wide screens and below it when narrow.
- the Descriptive Annual Metrics table labels its third column `Financial Metric
  Distribution Spread` and renders a one-dimensional percentile axis rather
  than descriptive prose;
- each inline axis uses fixed ticks at 0, 10, 25, median, 75, 90, and 100 and
  marks the selected company's numeric percentile; unavailable peer context
  remains explicitly unavailable;
- Current cross-sectional distribution and Metric History charts sit side by
  side on wide screens and stack on narrow screens. The current comparison
  summary and graph remain distinct from annual history.
  The Peer Distribution controls provide the metric and chart-type selections;
  cohort membership supplies the optional peer selection.
  - The metric is selected via a dropdown menu with the default being ROIC;
  - A completed analysis displays a current cohort summary and distribution
    graph. Selecting a cohort member adds a selected/peer comparison table and
    a second marker to the distribution chart.
  - The current comparison includes:
    1. The metric name.
    2. The metric description.
    3. The metric value.
    4. Industry (or best-fit group) distribution spread (90th percentile,
       75th percentile, median, mean, 25th percentile, and 10th percentile).
    5. Security's location within the distribution range.
    6. Percentile rank with the distribution.
    7. Interpretation of the metric's numeric position relative to the selected
       cohort and median, without converting percentile into an overall quality
       score or investment recommendation.
  - the current distribution graph type is selectable via dropdown;
    - Scatter plot
    - Histogram
    - Boxplot
  - The adjacent annual-history chart loads for the seven frozen Financial
    Profile metrics and changes with the selected peer. For any of the ten
    additional descriptive fields, the chart explicitly states that annual
    history is available for the seven core metrics. For supported metrics:
    - it shall be a bar graph;
    - initial chart will just be the security's historical data;
    - the default period is 5 years;
    - the user can select a period of 1 | 3 | 5 | 7 | 10 | All;
    - when a comparable security is selected, the chart shall show the selected security and the peer's historical data for the selected period;
    - the selected security's fiscal years define the chart's displayed anchor periods;
    - the peer's latest available annual observation aligns with the selected security's latest available observation, the second latest aligns with the second latest, and so forth;
    - each tooltip or accessible data label shall disclose the observation's actual annual statement date and filing-availability date;
    - historical EOEY tooltips shall also disclose the actual trading date used for its market-price input; this price is the latest trading close on or before the filing-availability date;
    - fiscal-year numbers do not need to match, and the dashboard shall not interpolate, prorate, or calendarize annual values;
    - the security with fewer valid annual observations determines the maximum comparable period and unsupported period controls shall be disabled;
  - the current comparison and annual-history charts default to the first
    available frozen Financial Profile metric;
  - the cohort-selection hierarchy is industry + market cap, industry, sector
    + market cap, sector, then the eligible market;
  - a cohort requires five finite observations; candidate and usable sample
    counts remain visible;
- explicit Passed, Failed, Unavailable, and Not applicable states; and
- sector-specific Graham and Magic Formula applicability explanations.
- Adhere to the Historical Financial Profile Comparison Contract in
  `../mvp/CONTRACT.md`.
- Each security identified by the contract's `limiting_tickers` shall have an
  asterisk affixed to its ticker within the Peer Distribution comparison. A
  Bootstrap warning alert below the historical chart shall explain the
  asterisk and identify the limiting security, selected metric, number of
  comparable observations, and covered anchor-period range. A fiscal-period
  offset warning by itself shall not add an asterisk.
- Only the historical chart container shall use the Bootstrap warning border
  color when `warning_codes` is non-empty. The current cross-sectional
  comparison table and distribution graph shall retain their normal borders.
- When paired annual statement dates differ by more than 183 days, Reveal shall
  disclose the maximum offset in a warning while continuing to display the
  otherwise valid comparison.
- When the peer has no valid annual observation available by the analysis
  cutoff, Reveal shall display a warning and render only the originally
  analyzed security's available history.


#### Current State

- Single page layout
- No navigation
- Distribution analysis
- Side-by-side comparison of other security within the cohort group
- Availability-aware annual selected/peer Financial Profile comparison

### Next Action

1. Add CI for the sanitized test and supported setup path.
2. Verify clean installation, tests, CLI, and dashboard launch from a release
   candidate checkout.
3. Complete public documentation and desktop/mobile demo artifacts.
4. Tag `v1.0.0` after the release gates pass; the feature freeze is not the
   release itself.
