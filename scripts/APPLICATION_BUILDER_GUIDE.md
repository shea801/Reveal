# APPLICATION BUILDER CONTRACT

This contract is to outline will direct the development of the application builder. It is an updatable contract
which will occur as the application grows and evolves.

THIS APPLICATION BUILDER CONTRACT IS HIERARCHICALLY UNDER `mvp/CONTRACT.md` AND ADHERES TO GUIDELINES AND STRUCTURE AS
INDICATED IN THE PROJECT 'README.md' AND THOSE FILES LOCATED IN 'look_here_first' DIRECTORY.


## Scope

The scope of the application builder contract is to provide a framework for the development of the application. It will 
outline the requirements and constraints for the development of the application which an agent can follow and use as an
instruction manual for building different aspects of the application. It will also outline the responsibilities 
of the parties involved in the development of the application. This contract will is to serve as sort of 'S.O.P.' guidebook
for creating each aspect of the application which will be responsible for security analysis procedure, selection, and dashboard
creation.

No analytical metric, ranking rule, threshold, or selection rule may be added solely because the value is available. Every displayed or ranked parameter must answer a defined user decision question.


## APPLICATION: "Reveal Investment Program"

- The applications working name will be "Reveal Investment Program"


## MISSION STATEMENT

The broader product vision below includes post-v1 possibilities. Reveal v1
analyzes eligible common stocks, presents evidence rather than a purchase
recommendation, and keeps ETF analysis outside its frozen scope.

To paraphrase Benjamin Graham, this is an application of practical counsel.
Reveal presents factual financial evidence and documented value-investing
methodologies to help users investigate eligible common stocks. It gives
supporting context, cautions, and missing-data explanations, not a buy/sell
verdict. ETF-specific analysis remains a possible post-v1 extension.

A secondary aspect of the application will be to provide a 'magic formula' ranking system as described by Joel Greenblatt in 
"The Little Book that 'Still' Beats the Market", as best implemented programmatically within this application.

Magic Formula ranking is a separate established-methodology lens, not a
Reveal-wide measure of investment quality.


## PARAMETERS

Using `mvp/CONTRACT.md` as the application-result reference, Reveal will
compile the values needed for security evaluation.
 

### General Vision:

- An entered security can receive an eligibility assessment; only eligible
  common stocks proceed to v1 analysis.
  - Some are Warrants, some are ETF's, some are Preferred Stocks, etc.
  - Reveal v1 analyzes eligible common stocks; ETF-specific analysis is post-v1.
- If a security fails eligibility, the user is told which requirement failed.
- The criteria will be based on the criteria as developed in the application 
  - companies with at least 5 consecutive years of financial data available
  - no 'Nano' market cap group companies
  - no Warrants or Convertible Securities
  - no Preferred Stocks
  - no Mutual Funds
- The Dash dashboard is the primary v1 entry point; the CLI remains a supported
  analysis and debugging interface.


### Security Selection: Financial Analysis and Graham Investor Types

#### Financial Profile

The Financial Profile is descriptive rather than a cumulative ranking. It
contains ROIC, Financial Profile ROC, FCFM, EOEY, Debt / Assets, Net Debt / FCF,
and EPS CAGR (4-Year Growth). Current peer context covers these seven plus ten
additional descriptive overview fields. Availability-aware selected/one-peer
annual history covers the seven core metrics; historical peer-cohort
distributions are post-v1. Relative position is not an investment-quality
verdict.

Financial Profile ROC uses annual EBIT over average capital employed. It is
separate from Magic Formula ROC, which keeps its TTM EBIT and quarter-aware
capital base for Magic Formula ranking.

#### Graham Defensive and Enterprising

Graham's criteria and applicability rules are documented in
`SELECTION_POLICY.md` and the result semantics in `../mvp/CONTRACT.md`.
The dashboard displays Passed, Failed, Unavailable, and Not applicable
separately. Graham does not supply the Magic Formula rank, and Financial
Profile context is not a tie-breaker for either methodology.

#### Magic Formula Ranking

The dashboard displays the latest persisted eligible-security ranking and the
selected security's methodology-specific rank when available. ROC and Earnings
Yield receive separate ordinal ranks; their sum determines the overall rank.
Availability-aware one-year-later comparisons are research/backtesting work,
not a current v1 dashboard view.
  
### DASHBOARD

The implemented dashboard begins with a Security text input, optional analysis
date, searchable Magic Formula ranking menu, and Analyze action. The text input
accepts a ticker, SEC-indexed company title, or CIK and offers suggestions
from stored SEC metadata. The menu shows the latest persisted quarterly Magic
Formula list in ascending rank order, labeled with rank, ticker, and company
name; choosing one fills the Security input. The menu does not follow the
optional analysis date. Both paths use the same eligibility and analysis
service after the user selects Analyze.

The Security Analysis overview includes identity, company description when
available, market context, current comparison-cohort membership, and a value
lens. Descriptive Annual Metrics displays seven frozen Financial Profile
metrics plus ten current overview fields with peer distributions. Annual
selected/peer history is available for the seven frozen metrics.
Graham criteria, Magic Formula ranking, and data-quality context remain
distinct. Historical cohort percentile distributions, ETF-specific analysis,
insider activity, and news are outside the current v1 dashboard slice.
