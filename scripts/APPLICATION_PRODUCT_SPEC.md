Project: Reveal
Version: v0.6.3 availability-aware annual comparison
Start date: 9/23/2026
Current work date: 10/09/2026

# APPLICATION PRODUCT SPEC

## Starter data deployment status

A selected SQLite starter archive can be prepared with
`investment-database-package export` and installed into a fresh data root
with `investment-database-package install`. This lets the included securities
be analyzed before an Alpha Vantage download. The archive still requires
content and redistribution review before it is added to a public release;
the current repository does not contain one. The full local databases remain
outside Git. See `README.md` for the commands and `docs/DATA_PIPELINE.md`
for the persistence boundary.

This file will describe the scope and purpose of the application.
This application lies within the 'Investment' project domain, and the current application working title is 'Reveal'
This file will tell:
- Who Reveal is for
- What problem it solves
- General User workflow
- Product principals

## APPLICATION BUILDER CONTRACT

This document outlines and directs the development of the application builder. It is an updatable document
which will occur as the application grows and evolves.

THIS APPLICATION_PRODUCT_SPEC.md IS HIERARCHICALLY UNDER `mvp/CONTRACT.md` AND ADHERES TO GUIDELINES AND STRUCTURE AS
INDICATED IN THE PROJECT 'README.md' AND THOSE FILES LOCATED IN 'look_here_first' DIRECTORY.


## Scope

The scope of the application builder document provides a framework for the development of the application. It 
outlines the requirements and constraints for the development of the application which an agent can follow and use as an
instruction manual for building different aspects of the application. It also outlines the responsibilities 
of the parties involved in the development of the application. This document is to serve as an 'S.O.P.' guidebook
for the problem this application looks to solve, identifying this application's intended audience, the general user 
work-flow,and the principals the application will adhere too.

No analytical metric, ranking rule, threshold, or selection rule may be added solely because the value is available. 
Every displayed or ranked parameter must answer a defined user decision question.


## APPLICATION: "Reveal"

- The applications working name is "Reveal"


## MISSION STATEMENT

The following is for long-term product direction, not a list of completed v1
features. Reveal v1 presents evidence and methodology-specific context; it
does not tell a user whether to buy a security.

To paraphrase Benjamin Graham, 'this is an application of practical counsel.'  
1. Its purpose is to provide information on common stock securities and, post-v1.0, ETF's derived from the principles 
   established by Benjamin Graham and built upon by many others.
2. The information is presented to a user in a fashion that shows the relative strength or weakness of a chosen security 
   as it relates to its own history and its industry and market-cap-group peers (including over time). 
3. This application provides as much factual financial information as programmable through a dashboard interface.
4. It aims to support an informed investigation without making a purchase
   recommendation.
5. Information is provided for securities within the supported scope.
6. Each analysis shows supporting evidence, cautions, and missing-data
   context rather than a buy/sell verdict.
7. The information is presented in clear and succinct manner which anyone can understand.

A complimentary aspect of the application provides a 'magic formula' ranking system as described by Joel Greenblatt in 
"The Little Book that 'Still' Beats the Market", as best implemented, programmatically, within this application.

- The Magic Formula is a separate, established ranking lens for eligible securities, not a Reveal-wide investment-quality 
  score.
- The securities ranked in the 'magic formula' are those that meet certain qualifying criteria, so not all securities 
  will have a magic formula ranking (for ex: only US based companies, minimum Small market cap, etc.)
- A security under analysis will have the ranking explained in terms of its
  Return on Capital rank, Earnings Yield rank, and their combined ordinal score
  among qualifying securities.
- Once a particular company is selected from the 'magic formula' list, its other financial metrics are shown to allow 
  the user to make a better informed decision on the particular security.


## PARAMETERS

Using `mvp/CONTRACT.md` as the application-result reference, Reveal will
compile the values needed for security evaluation.
 

### General Vision (post-v1 direction unless listed as implemented below):

- The longer-term product may broaden security coverage, but v1 analyzes only
  eligible common stocks and does not recommend purchase.
  - Some are Warrants, some are ETF's, some are Preferred Stocks, etc.
  - ETF-specific analysis requires a future policy and is outside v1.
- The analytical criteria will be based on the financial metrics as developed in the application
- There will be guardrails applied to securities so the user will know WHY a security, which is listed as US 
  tradeable security, does not meet the criteria:
  - companies must have at least 5 consecutive years of financial data available
  - no 'Nano' market cap group companies
  - no Warrants or Convertible Securities
  - no Preferred Stocks
  - no Mutual Funds
- The initial Dash dashboard is the primary application entry point; the CLI remains a supported analysis and debugging 
  interface.
- An analysis of a security will be presented with derived explanations based on the values calculated by the application.
- The intended purpose of this application is to provide understandable financial metrics for a company the user is
  interested in purchasing.
- The intended user is not expected to be a financial professional.
- The intended user is: 
  - Someone who may not have any familiarity with financial analysis, but may have a retirement plan.
  - Someone who is simply interested in investing, or interested in a particular company.
  - Someone who is looking to start investing their money, but doesn't know what companies to invest in.
  - Someone who wants to know why a particular company is in their retirement plan's portfolio.
  - Anyone who wants to understand the financial metrics of a company.
- The application will provide explanations for the metrics presented from a 'value' investor's perspective.
- The application will explain risk, margin of safety, intrinsic value, and other relevant concepts from principles 
  derived from value investing.
- Investor's patience and understanding the importance of continuous compounding will also be principal concepts explained.
- The information shall be presented on an interactive dashboard.

### Implemented in Reveal v1

* Ticker, SEC company-name, and CIK lookup.
* Magic Formula ranked-security selection.
* Common-stock eligibility assessment.
* Seven frozen Financial Profile metrics plus ten additional current
  descriptive fields, with current peer distributions.
* Availability-aware annual history for the selected security and one peer
  across the seven frozen metrics.
* Graham and Magic Formula analysis.

### Post-v1 product direction

* Independent sector and industry browsing.
* Market-cap-based security discovery.
* ETF analysis.
* Historical peer-cohort distributions and broader historical cohort analysis.
* Insider and qualitative research.
