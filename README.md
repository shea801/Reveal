Project: Reveal
Version: v1.0.0
Working tree: post-tag runtime configuration update; package version remains 1.0.0

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

**Reveal v1.0.0 is tagged; this working tree contains a post-tag setup change.**

The core ingestion, persistence, data-access, analytics, point-in-time
metadata, Magic Formula ranking, backtesting, CLI, and automated-test
infrastructure are substantially implemented. Package version `1.0.0` includes
a single-security Dash interface over the application contract, with selectable
current peer distributions for seven core Financial Profile metrics and ten
additional descriptive overview metrics, plus compact percentile spreads
directly in the Descriptive Annual Metrics table. It also exposes
presentation-ready comparison-cohort membership from inexpensive persisted
company metadata, plus availability-aware annual history for the selected
security and one requested peer. Security entry accepts a ticker, SEC-indexed
company name, or CIK, and a separate menu lists the latest persisted Magic
Formula ranking by rank, ticker, and company name. The repository includes a
CI workflow and a local `v1.0.0` tag. The data-root change below is being
applied after that tag while the package version remains `1.0.0`; it is not
part of the tagged snapshot. A starter ZIP is prepared locally for a separate
release upload and is present in under the `dist/` directory along with the 
`*.whl` and `*.tar.gz` files upon downloading from the GitHub repository.

## Why I Built This

Reveal began as a personal project to better understand long-term
investing, retirement planning, and the value-investing principles
introduced by Benjamin Graham in *The Intelligent Investor*.

As the project grew, it became an end-to-end software and data
engineering project involving Python, SQL, ETL workflows, relational
data modeling, external APIs, financial-statement normalization,
point-in-time historical analysis, automated testing, and application
design.

The current objective is to maintain and extend the usable application while
preserving the analytical transparency that drove the project from the
beginning.

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
The annual-history comparison and strict backtesting workflows use SEC filing
availability to avoid displaying financial statements before their matched
filings were public. Ordinary single-security analysis selects statements by
fiscal period, not by SEC filing availability.

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

For ordinary single-security analysis, the seven frozen metrics use the latest
completed annual fiscal period on or before the requested analysis date. This
does not guarantee the filing was public by that date. ROIC uses annual NOPAT
over average invested capital;
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
- Automated tests for core application behavior.

## Repository Structure

``` text
Reveal/
├── data_ingestion/              # External API ingestion and security discovery
├── data_access/                 # Database-backed financial and market-data access
├── analytics/                   # Financial calculations and analytical methods
├── dashboard/                   # Dash presentation layer and styles
├── mvp/                         # Stable application models and service boundary
├── runtime_config/              # Data-root selection, database paths, and API key
├── Securities_DB/               # SQLite persistence, migrations, and DB helpers
├── maintenance/                 # Recurring update and maintenance workflows
├── scripts/                     # CLI entry points and operational commands
├── docs/                        # Technical pipeline, SEC, and backtest docs
├── Tests/                       # Automated tests
└── .github/                     # Continuous integration workflow
```

An existing data root may additionally contain ignored `Securities/`,
`ETF_Securities/`, `All_Tickers_Searched/`, and `notebooks/` directories.
Those are data/maintenance paths, not directories supplied by a fresh clone.

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
If there is no pre-existing data root, the application will create one
upon download and place the data root in the `reveal-data` directory with
`Securities_DB/` as a subdirectory (detailed below).

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
git clone https://github.com/shea801/Reveal.git
cd Reveal
python3 scripts/setup_project.py
source .venv/bin/activate
```

The setup helper creates or reuses `.venv`, installs the project
dependencies, and validates runtime imports. It does not create a private
configuration file or move any data.
Activate the environment before using the installed CLI commands or `pytest`.
On Windows PowerShell, run the setup helper with
`py -3 scripts/setup_project.py`, then activate with
`.venv\Scripts\Activate.ps1` instead.

This working tree selects the data root in this order: `REVEAL_DATA_ROOT` if
set, the per-user `data_root` saved by `runtime_config.set_data_root(...)`,
then the platform's default per-user directory. The default directory is
created on first use; databases and source data are **not** created with it.

| Platform | Default data root | Saved config file |
| --- | --- | --- |
| macOS | `~/Library/Application Support/Reveal/data` | `~/Library/Application Support/Reveal/config.toml` |
| Windows | `%LOCALAPPDATA%\Reveal\data` | `%APPDATA%\reveal\config.toml` |
| Linux | `~/.local/share/reveal` (or `$XDG_DATA_HOME/reveal`) | `~/.config/reveal/config.toml` (or `$XDG_CONFIG_HOME/reveal/config.toml`) |

To keep using an existing populated data directory, save it once:

``` bash
python -c 'from runtime_config import set_data_root; set_data_root("/absolute/path/to/existing/data-root")'
```

Alternatively, set `REVEAL_DATA_ROOT` to an existing absolute directory for
the current shell or process. It overrides the saved choice. For a checkout
whose data remains in its checkout directory, point either setting there; no
files need to be relocated. For example:

``` bash
export REVEAL_DATA_ROOT="/absolute/path/to/existing/data-root"
```

Use `export REVEAL_DATA_ROOT="$PWD"` only when the current directory is the
existing data root (for example, a development checkout that already contains
`Securities_DB/investment.db`). It does not mean any working directory will do.

PowerShell: `$env:REVEAL_DATA_ROOT = 'C:\path\to\existing\data-root'`.
Explicit environment and saved roots must be absolute, existing directories.
To create and save a new empty root, call
`set_data_root("/absolute/path/to/new-root", create=True)` before installing
or loading data. Keep runtime settings out of tracked project files. Under
the selected root, Reveal expects the existing layout:

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

As there is no full database to download, the dashboard does not need it to
run the dashboard. A downloadable `*.zip` file is available upon application 
download to supply the information needed by the dashboard. When created, the 
investment database is used for analysis, and the Magic Formula database supplies 
the ranked menu when current data is populated. Data ingestion and maintenance use 
the JSON and CSV paths. `ALPHAVANTAGE_API_KEY` is required only for live Alpha Vantage 
requests made by ingestion and refresh jobs. Set it in the local environment before
those operations; it is not needed to import modules, run unit tests, or start
the dashboard. Existing ignored `configuration.py` files are no longer read
by the application.

### Starter databases for a fresh checkout

Reveal's full investment database is several GB and is intentionally
excluded from the public repository and Python package.

A smaller demonstration dataset is prepared as a ZIP for separate upload to
the GitHub v1.0.0 Release. The archive is not tracked in Git.

The starter archive contains historical financial statements, market
prices, SEC filing metadata, and calculated ranking results for
12 selected securities:

AAPL, AMZN, CAT, GOOGL, HD, JNJ, JPM, KO, MSFT, NEE, PG, and XOM.

#### Install the starter database

Use a local copy of `Reveal_starter_v1.0.0.zip`, or download it from the
v1.0.0 GitHub Release after it is attached there. It is found in the `dist/`
director under the chosen/selected 'Reveal' directory.

Create and save an empty directory for Reveal's data:

```bash
python -c 'from runtime_config import set_data_root; set_data_root("~/reveal-data", create=True)'
```

Install the archive:

```bash
investment-database-package install \
  --bundle "$HOME/Downloads/Reveal_starter_v1.0.0.zip"
```

Adjust the archive path to the local copy you obtained. If `--data-root` is
passed to the installer, it applies only to that command; save the same root
with `set_data_root(...)` or set `REVEAL_DATA_ROOT` for later dashboard runs.

The installer creates the following directory structure:

```text
reveal-data/
└── Securities_DB/
    ├── investment.db
    └── magic_formula_results.db
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

The installer validates archive checksums, SQLite integrity, and foreign-key
references before installation. It refuses to overwrite existing databases
and restores the original destination state if installation fails.

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
source archives are not committed to the public repository. The size-limited
starter archive is prepared for a separate release upload, not in Git.

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

## Release Status

The v1 feature set is frozen. Package metadata remains `1.0.0`, and the local
`v1.0.0` Git tag identifies the earlier release snapshot. This working tree
adds the new data-root behavior after that tag; a future `v1.0.1` version bump
has not been made. CI installs the package, runs the sanitized tests and Ruff,
builds a distribution, and checks wheel imports. The starter ZIP is prepared
for separate upload as a GitHub Release asset. Demo screenshots or recordings
are not included in this repository.

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
- Ordinary single-security analysis selects fiscal statement periods on or
  before the requested date; unlike historical comparison and strict
  backtesting, it does not gate each statement on SEC filing availability.
- Eligibility requires five distinct annual statement dates spanning at least
  four years per required statement type; the preflight does not verify every
  intervening fiscal year is present.
- Historical-universe analysis may contain survivorship bias.
- Source providers may omit or shorten adjusted-price history for
  individual securities.
- Financial comparisons require context and do not independently
  establish whether a security is an appropriate investment.

## Development Workflow and AI Assistance

This project is developed with support from AI coding assistants,
including ChatGPT, Codex, and Claude. I wrote the original code to this project.
I had a model, a file system, and a small database to support development. AI acted 
as a project manager to help keep the development process on track, as a programmer
and code reviewer, and as a tutor to help better learn and understand the 
engineering and development process.

AI tools are used for implementation support, refactoring, testing,
documentation, and technical review. Architecture, analytical
methodology, requirements, integration decisions, and final validation
remain owner-directed. AI has been a tremendous asset to the development
process. It has also shown the need for detailed review of it's work, which 
has contributed as much to learning more about software development than 
trying to write more code.

## Author

**Shea Hanson**  
Python developer and data analyst with a career background in
fire-service leadership, focused on building practical data-intensive
applications.
