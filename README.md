Project: Reveal
Version: v0.6.3 availability-aware annual comparison
Current work date: 10/09/2026

# Reveal — Investment Analysis Platform

Reveal is a Python-based financial analysis application that transforms
market, financial-statement, and SEC filing data into explainable
security analysis. The project combines external API ingestion, SQLite
persistence, point-in-time financial data, analytical services,
established value-investing frameworks, historical comparison, and a
user-facing application layer.

Reveal is designed to present financial evidence and context. It does
not attempt to produce a proprietary “best stock” score or investment
recommendation.

## Project Status

**Reveal v1 feature freeze — release preparation in progress.**

The core ingestion, persistence, data-access, analytics, point-in-time
metadata, Magic Formula ranking, backtesting, CLI, and automated-test
infrastructure are substantially implemented. Package version `0.6.3` includes
a single-security Dash interface over the application contract, with selectable
current peer distributions for seven core Financial Profile metrics and ten
additional descriptive overview metrics, plus compact percentile spreads
directly in the Descriptive Annual Metrics table. It also exposes
presentation-ready comparison-cohort membership from inexpensive persisted
company metadata, plus availability-aware annual history for the selected
security and one requested peer. Security entry accepts a ticker, SEC-indexed
company name, or CIK, and a separate menu lists the latest persisted Magic
Formula ranking by rank, ticker, and company name. Historical cohort percentile
distributions remain outside this v1 slice. Representative dashboard, security
selection, peer, and annual-history validation is complete. The feature freeze
does not constitute a `v1.0.0` release: CI, clean release verification, and
public documentation/demo artifacts remain open.

## Why I Built This

Reveal began as a personal project to better understand long-term
investing, retirement planning, and the value-investing principles
introduced by Benjamin Graham in *The Intelligent Investor*.

As the project grew, it became an end-to-end software and data
engineering project involving Python, SQL, ETL workflows, relational
data modeling, external APIs, financial-statement normalization,
point-in-time historical analysis, automated testing, and application
design.

The current objective is to turn that infrastructure into a complete,
usable application while preserving the analytical transparency that
drove the project from the beginning.

## What Reveal Does

Reveal accepts a security for analysis and combines stored financial,
market, and filing data into a structured security-analysis result.

The application is designed to present several distinct analytical
lenses rather than collapse them into a single proprietary ranking:

- **Financial Profile** — capital efficiency, cash generation,
  balance-sheet condition, and earnings growth, with current peer-distribution
  context and availability-aware annual selected/peer comparison.
- **Graham Analysis** — Defensive and Enterprising criteria based on the
  project’s documented Graham-style methodology.
- **Magic Formula** — Joel Greenblatt-style Return on Capital and
  Earnings Yield ranking for the eligible common-stock universe.
- **Historical Context** — dashboard comparison of annual Financial Profile
  values for the selected security and one peer, aligned by recency while
  retaining each security's actual fiscal and filing-availability dates.
- **Data Quality Context** — explicit warnings and exclusions when
  required history, filing identity, or adjusted-price data is
  unavailable.

The dashboard runs a common-stock eligibility preflight before analysis and
keeps Failed, Unavailable, and Not applicable criteria visibly distinct.

Detailed product and analytical policy belongs in the project
specification documents rather than in this README.

## Key Engineering Features

### Point-in-Time Financial Analysis

Reveal distinguishes among the requested analysis date, fiscal statement
periods, actual market-price dates, and SEC filing availability.
Historical workflows are designed to avoid using financial statements
before the information was publicly available.

### SEC Filing Availability Layer

SEC filing metadata is normalized by CIK and accession number. Statement
matches retain their match method, confidence, and ticker/CIK identity
status so that ambiguous historical relationships remain visible instead
of being silently accepted.

### Historical Price Integrity

The OHLCV data model stores raw and adjusted price information together
with dividend and split data. Missing adjusted-price history remains
explicitly unavailable rather than being replaced with raw closing
prices in total-return calculations.

### Layered Application Architecture

The project separates external ingestion, persistence, data access,
analytics, application services, and presentation. Financial
calculations are kept outside the dashboard so that analytical behavior
can be tested independently from the user interface.

### Explainable Analytics

Reveal keeps different analytical methods distinct. Financial-profile
comparisons describe company characteristics; Graham analysis applies
documented criteria; Magic Formula ranking remains a separate
established ranking methodology.

### Automated Validation

The repository includes automated tests across data access, analytical
calculations, application-service behavior, database workflows, and
historical-analysis logic. The project setup also validates installed
dependencies and core runtime imports.

## Architecture

``` text
External Sources
      |
      +-- Alpha Vantage
      +-- SEC Filing Metadata
              |
              v
        Data Ingestion
              |
              v
      SQLite Persistence
              |
              v
         Data Access
              |
              v
          Analytics
      +-------+--------+
      |       |        |
 Financial  Graham   Magic Formula
 Profile    Analysis    Ranking
      +-------+--------+
              |
              v
     Application Service
              |
              v
   SecurityAnalysisResult + companion results
              |
              v
      Reveal Dashboard
```
`mvp.models.SecurityAnalysisResult` is the principal security-analysis result.
The service also returns eligibility, ranked-selector, current-distribution,
cohort-membership, and annual-history companion models. Graham and Magic
Formula are separate analytical lenses, not stages of one another.

The intended data flow is one-directional: presentation consumes the
application/service contract rather than reaching directly into
persistence or duplicating analytical calculations.

## Financial Analysis Approach

Reveal’s general Financial Profile is descriptive rather than a
proprietary security-ranking system.

The seven frozen Financial Profile metrics are:

- Return on Invested Capital (ROIC)
- Financial Profile Return on Capital (ROC)
- Free Cash Flow Margin (FCFM)
- Estimated Owner Earnings Yield (EOEY)
- Debt / Assets
- Net Debt / Free Cash Flow
- EPS CAGR (4-Year Growth)

The dashboard also displays ten current descriptive overview fields: gross
margin, free cash flow, estimated owner earnings, operating income, inventory
turnover, return on assets, return on equity, liabilities to equity,
long-term debt to cash-flow-adjusted cash, and interest coverage. Current peer
distributions cover all 17 fields; selected-security/one-peer annual history
currently covers the seven frozen metrics. Magic Formula ROC, earnings yield,
and rank belong to a separate ranking methodology, not this metric set.

The seven frozen metrics use the latest completed annual data available to the
requested analysis date. ROIC uses annual NOPAT over average invested capital;
Financial Profile ROC uses annual EBIT over average capital employed; FCFM uses
operating cash flow less capital expenditures divided by revenue; and EOEY uses
that same cash-flow amount as a documented owner-earnings proxy divided by
point-in-time market capitalization. EPS CAGR (4-Year Growth) uses five aligned
annual EPS observations with positive endpoints, representing four
year-over-year compounding intervals.

Financial Profile ROC is not the Magic Formula ROC. The profile value is a
descriptive annual operating-efficiency metric based on average capital
employed. Magic Formula ROC retains its methodology-specific TTM EBIT and
quarter-aware capital base because it is an input to cross-sectional ordinal
ranking. The two values answer different questions and should not be compared
as interchangeable calculations.

The application is intended to show the actual metric value together
with relevant historical and peer context. Statistical comparisons
should describe where a security lies within a distribution rather than
imply that peer position alone makes a company a good or bad investment.

Graham Defensive/Enterprising analysis and Magic Formula ranking remain
separate methodologies with their own eligibility and calculation rules.

See the product and selection-policy documents for the detailed
analytical contract.

## Current Capabilities

The repository currently supports:

- Alpha Vantage financial-statement, company, and OHLCV ingestion.
- Normalized local SQLite persistence.
- Local security and ETF reference datasets.
- Shared financial-statement and market-date selection.
- Financial quality and valuation calculations.
- Graham-style Defensive and Enterprising analysis.
- Magic Formula Return on Capital and Earnings Yield ranking.
- Quarter-by-quarter Magic Formula result persistence.
- SEC filing and acceptance metadata import from a local bulk archive.
- Ticker/CIK identity tracking and statement-to-filing matching.
- Adjusted-price backfill and corporate-action-aware return data.
- Availability-aware Magic Formula backtesting.
- A stable `SecurityAnalysisResult` application model.
- CLI analysis for one or more securities.
- A single-page Reveal dashboard for contract-shaped security analysis.
- Dashboard lookup by ticker, SEC company name, or CIK, with suggestions from
  persisted SEC ticker metadata and an explicit analysis action.
- A searchable Magic Formula selector ordered by the latest persisted
  quarterly rank, showing rank, ticker, and company name.
- Company description in the Security Analysis overview when available from
  stored company details.
- Selectable current peer distributions for all 17 descriptive annual metrics,
  with percentile, quartile, sample-size, and cohort context.
- Compact descriptive-metric distribution spreads with fixed percentile ticks
  and a marker for the selected company's position.
- Metadata-only comparable-security cohorts containing ticker, company name,
  industry, sector, and market-cap classification without running full peer
  analyses.
- Availability-aware annual Financial Profile comparison for the selected
  security and one peer, with dynamic periods, source-date disclosure, limiting
  history warnings, and fiscal-period offset warnings.
- Jupyter notebooks for exploratory research and development.
- Automated tests for core application behavior.

## Repository Structure

``` text
Investment/
├── data_ingestion/              # External API ingestion and security discovery
├── data_access/                 # Database-backed financial and market-data access
├── analytics/                   # Financial calculations and analytical methods
├── dashboard/                   # Dash presentation layer and styles
├── mvp/                         # Stable application models and service boundary
├── Securities_DB/               # SQLite persistence, migrations, and DB helpers
├── maintenance/                 # Recurring update and maintenance workflows
├── scripts/                     # CLI entry points and operational commands
├── docs/                        # Technical pipeline, SEC, and backtest docs
├── Tests/                       # Automated tests
├── notebooks/                   # Exploratory analysis and development notebooks
├── Securities/                  # Local company datasets (ignored in git)
├── ETF_Securities/              # Local ETF datasets (ignored in git)
├── All_Tickers_Searched/        # Local search datasets (ignored in git)
├── investing_literature_pdfs/   # Local reference material
└── look_here_first/             # Project context and architecture documentation
```

The initial dashboard is implemented in `dashboard/` and launched with
`investment-dashboard`. It consumes `mvp.service` and does not duplicate
analytical calculations.

### Major Responsibilities

**`data_ingestion/`**  
Retrieves external market and financial data and supports security
discovery.

**`Securities_DB/`**  
Owns SQLite persistence, schema evolution, database helpers, Magic
Formula results, OHLCV storage, and SEC metadata storage.

**`data_access/`**  
Provides database-backed access to financial statements, company
details, prices, and SEC filing metadata using shared date-selection
rules.

**`analytics/`**  
Contains financial calculations, Graham analysis, Magic Formula logic,
market analytics, and historical backtesting.

**`mvp/`**  
Defines the stable application-facing `SecurityAnalysisResult` model and
the service that maps analytical outputs and comparison metadata into stable
application contracts.

**`scripts/` and `maintenance/`**  
Provide installed command-line workflows for analysis, data updates,
database building, backtesting, and maintenance.

## Quick Start

Python 3.11 through 3.14 is supported.

### 1. Clone and set up the project

``` bash
git clone https://github.com/shea801/Investment.git
cd Investment
python scripts/setup_project.py
```

The setup helper creates or reuses `.venv`, installs the project
dependencies, and validates runtime imports. It does not create a private
configuration file or move any data.

Set `REVEAL_DATA_ROOT` to the **existing, absolute directory** that contains
Reveal's persisted data. The directory must exist. For a development checkout
whose data remains in its checkout directory, point the variable to that
directory; no files need to be relocated. For example:

``` bash
export REVEAL_DATA_ROOT="/absolute/path/to/existing/data-root"
```

PowerShell: `$env:REVEAL_DATA_ROOT = 'C:\path\to\existing\data-root'`.
Keep this setting in your local shell or environment configuration, not in a
tracked project file. Under that root, Reveal expects the existing layout:

``` text
Securities_DB/investment.db
Securities_DB/magic_formula_results.db
Securities/
ETF_Securities/
All_Tickers_Searched/
company_tickers.json
notebooks/magic_formula_tickers.csv
notebooks/magic_formula_ranked_securities.csv
```

Existing root-level CSV files such as `all_ticker_symbols.csv`,
`valid_etf_tickers.csv`, and `magic_formula_tickers.csv` retain their current
locations. Not every file is needed for dashboard startup: the investment
database is needed for analysis, and the Magic Formula database supplies the
ranked menu when present. Data ingestion and maintenance use the JSON and CSV
paths. `ALPHAVANTAGE_API_KEY` is required only for live Alpha Vantage requests
made by ingestion and refresh jobs. Set it in the local environment before
those operations; it is not needed to import modules, run unit tests, or start
the dashboard. Existing ignored `configuration.py` files are no longer read
by the application.

### Starter databases for a fresh checkout

Reveal's full investment database is several GB and is intentionally
excluded from the public repository and Python package.

A smaller demonstration dataset is distributed separately as a ZIP
asset attached to the GitHub v1.0.0 Release.

The starter archive contains historical financial statements, market
prices, SEC filing metadata, and calculated ranking results for
12 selected securities:

AAPL, AMZN, CAT, GOOGL, HD, JNJ, JPM, KO, MSFT, NEE, PG, and XOM.

#### Install the starter database

Download `Reveal_starter_v1.0.0.zip` from the v1.0.0 GitHub Release.

Create an empty directory for Reveal's data:

```bash
mkdir -p "$HOME/reveal-data"
```

Install the downloaded archive:

```bash
investment-database-package install \
  --bundle "$HOME/Downloads/Reveal_starter_v1.0.0.zip" \
  --data-root "$HOME/reveal-data"
```

Adjust the archive path if your browser saved the ZIP elsewhere.

The installer creates the following directory structure:

```text
reveal-data/
└── Securities_DB/
    ├── investment.db
    └── magic_formula_results.db
```

Configure Reveal to use the installed databases:

```bash
export REVEAL_DATA_ROOT="$HOME/reveal-data"
```

Launch the dashboard:

```bash
investment-dashboard
```

Alternatively, analyze an included security from the command line:

```bash
investment-analyze AAPL --format json
```

#### Data availability and limitations

The starter database is a historical demonstration snapshot, not a
live market-data feed. Its financial statements, market prices, and
company information may be outdated.

Analyses and peer comparisons are limited to the securities and
historical observations included in the archive.

An Alpha Vantage API key is not required to analyze securities using
the installed starter database. Live ingestion and refresh operations
require the `ALPHAVANTAGE_API_KEY` environment variable.

The installer validates archive checksums and SQLite integrity before
installation. It refuses to overwrite existing databases.

#### Creating custom starter archives

Developers with existing populated databases can create their own
starter archives using `investment-database-package export` and
explicitly selected ticker symbols.

Review the selected data, archive contents, and applicable
redistribution rights before distributing an exported archive.

### 2. Run the automated tests

``` bash
pytest Tests
```

### 3. Analyze a security from the CLI

``` bash
investment-analyze AAPL
```

For a historical analysis date and JSON output:

``` bash
investment-analyze AAPL --analysis-date 2024-12-31 --format json
```

### 4. Run the Reveal dashboard

``` bash
investment-dashboard
```

Open `http://127.0.0.1:8050`. Use `--host` or `--port` to change the local
server binding. Enter a ticker, SEC-indexed company name, or CIK, or choose a
security from the Magic Formula ranking menu. The menu shows the latest
persisted quarter available when the dashboard starts; it does not change with
the optional analysis date. Choosing a ranked security fills the Security
field; select Analyze to run the eligibility check and analysis. The dashboard
explains ineligible selections and renders Overview, the 17-row descriptive
annual metrics table, selectable peer-distribution charts, Graham analysis,
Magic Formula results, and data-quality warnings for eligible common stocks.

## Data Sources

Reveal currently uses:

- **Alpha Vantage** for company financial statements, company
  information, and daily market-price data.
- **SEC ticker/CIK datasets** for company identifier mapping.
- **SEC bulk submissions metadata** for filing dates, acceptance
  timestamps, forms, and accession numbers.

Large local datasets, API credentials, full database files, and downloaded
source archives are not intended to be committed to the public repository.
A reviewed, size-limited starter database archive is the sole planned
exception.

## Technical Documentation

Detailed operational and historical-analysis documentation is separated
from the README:

- `docs/DATA_PIPELINE.md` — ingestion, persistence, update
  flow, data ownership, and data-quality behavior.
- `docs/SEC_POINT_IN_TIME.md` — SEC filing availability,
  statement matching, ticker/CIK identity, and point-in-time
  limitations.
- `docs/BACKTESTING.md` — Magic Formula historical cohort
  construction, price selection, exclusions, outputs, and known
  limitations.

Product behavior and analytical policy are documented in
`scripts/APPLICATION_PRODUCT_SPEC.md`, `scripts/SELECTION_POLICY.md`,
`scripts/DASHBOARD_SPEC.md`, and `scripts/APPLICATION_BUILDER_GUIDE.md`.

## v1.0 Completion Target

Reveal v1.0 is complete when a user can select an eligible common stock
and receive a coherent, explainable analysis through a usable interface
backed by the existing data and analytical infrastructure, with
reproducible installation and automated validation.

The v1 feature set is frozen. The remaining critical path is:

1. Add CI for the sanitized test and supported setup path.
2. Verify a clean install, tests, and dashboard/CLI launch from a release
   candidate checkout.
3. Complete public documentation and capture representative demo artifacts.
4. Tag `v1.0.0` only after those release gates pass.

## Post-v1 Ideas

Potential later work includes:

- insider transaction context;
- company, industry, and institutional “scuttlebutt” or news context;
- ETF-specific analytical policy;
- broader availability-aware historical validation;
- additional historical ticker/CIK identity research;
- research notebooks exploring statistical or machine-learning questions
  without making them dependencies of the core application.

These items are intentionally outside the v1.0 critical path.

## Known Limitations

- Reveal is educational and research-oriented and is not financial
  advice.
- Alpha Vantage normalized financial values are not accession-pinned;
  later restatements may therefore affect historical financial values
  even when SEC metadata controls information timing.
- Historical ticker/CIK identity is not complete for every security.
- Historical-universe analysis may contain survivorship bias.
- Source providers may omit or shorten adjusted-price history for
  individual securities.
- Financial comparisons require context and do not independently
  establish whether a security is an appropriate investment.

## Development Workflow and AI Assistance

This project is developed with support from AI coding assistants,
including ChatGPT, Codex, and earlier Claude-assisted work.

AI tools are used for implementation support, refactoring, testing,
documentation, and technical review. Architecture, analytical
methodology, requirements, integration decisions, and final validation
remain owner-directed.

## Author

**Shea Hanson**  
Python developer and data analyst with a career background in
fire-service leadership, focused on building practical data-intensive
applications.
