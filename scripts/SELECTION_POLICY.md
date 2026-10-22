Project: Reveal
Version: v0.6.3 availability-aware annual comparison
Start date: 9/23/2026
Current work date: 10/09/2026

# SELECTION POLICY

This file will describe the selection policy for the application.
This application lies within the 'Investment' project domain, and the current application working title is 'Reveal'
This file will define:
- Eligible Securities
- Financial Profile analysis
- Defensive criteria
- Enterprising criteria
- Magic Formula
- Insider Information
- Missing-data rules


## ELIGIBLE SECURITIES

Reveal v1 analysis eligibility uses the following requirements; eligibility
is not a purchase recommendation:
- All securities must be publicly traded on a major stock exchange.
- Securities must be listed in the United States.
- Reveal v1 evaluates common stocks. ETF-specific analysis is deferred until
  its selection and analytical policy is defined.
- No Mutual Funds
- No Warrants
- No Options or Futures
- No preferred stocks or convertible securities
- No bonds
- No US Treasuries
- Securities must have a minimum market capitalization of $250 million (Small market cap group).
- Securities must have a minimum of 5 consecutive years of financial data available.
- The 'Defensive' and 'Enterprising' investor types will have other limiting financial factors which will exclude certain securities from consideration.


### Financial Profile

Financial Profile analysis is descriptive and does not create a cumulative or
ordinal Reveal ranking. Its seven frozen core metrics are:

1. Return on Invested Capital (ROIC): annual NOPAT divided by average annual
   invested capital.
2. Financial Profile Return on Capital (ROC): annual EBIT divided by average
   annual capital employed.
3. Free Cash Flow Margin (FCFM): annual operating cash flow less capital
   expenditures, divided by annual revenue.
4. Estimated Owner Earnings Yield (EOEY): the OCF-less-capex amount,
   explicitly treated as an owner-earnings proxy, divided by point-in-time
   market capitalization.
5. Debt to Assets: annual interest-bearing debt divided by total assets.
6. Net Debt to Free Cash Flow: annual interest-bearing debt less cash and
   short-term investments, divided by positive annual free cash flow.
7. EPS CAGR (4-Year Growth): Calculates compound annual EPS growth
   using five consecutive, aligned annual EPS observations, representing four
   elapsed years and four annual compounding intervals. Both the beginning and
   ending EPS values must be positive.

The dashboard also shows ten additional current descriptive fields: gross
margin; free cash flow (annual operating cash flow less capital expenditures);
estimated owner earnings (the same proxy, not a full reconstruction); operating
income (revenue less cost of goods and services sold and operating expenses);
inventory turnover (annual revenue / selected annual inventory balance);
return on assets (annual net income / annual total assets); return on equity
(annual net income / annual shareholders' equity, falling back to assets less
liabilities); liabilities to equity (annual total liabilities / annual equity;
the underlying field is named `debt_to_equity`); long-term debt to
cash-flow-adjusted cash (annual long-term debt / cash plus annual free cash
flow); and interest coverage (annual EBIT / annual interest expense).

Current cross-sectional distributions cover all 17 descriptive fields. Annual
selected-security/one-peer history covers the seven frozen core metrics. Those
metrics use latest completed annual data available at the analysis cutoff;
EOEY also uses a point-in-time market-capitalization input. Magic Formula ROC,
earnings yield, and overall rank belong to a separate methodology. Its ROC
uses TTM EBIT and a quarter-aware capital base for ordinal ranking, while
Financial Profile ROC describes annual operating efficiency. Both must be
labeled with their calculation when shown together.


### FINANCIAL METRIC ASSESSMENT

**Implementation status:** Reveal v1 provides current cross-sectional peer
distributions for the 17 descriptive fields and availability-aware annual
history for the selected security and one peer for the seven frozen metrics.
Historical peer-cohort distributions and generalized economic benchmarks are
post-v1 research, not v1 requirements. The possible reference frames are:

1. Current peer distribution (implemented).
2. Historical peer-cohort distribution (post-v1).
3. Selected-security/one-peer annual history (implemented for seven core
   metrics); broader company-history distributions are post-v1.
4. Economic/fundamental benchmark where defensibly applicable (post-v1).

No universal benchmark will be assigned solely for
convenience.

Peer groups will preferentially use industry and market-cap
comparables, with broader groups used when sample size is
insufficient:

1. Industry + similar market cap
        
if sample too small:
        ↓
2. Industry
        
elif sample too small:
        ↓
3. Sector + similar market cap

elif sample too small:
        ↓
4. Sector

elif sample too small:
        ↓
5. Broad market

The current cross-sectional dashboard implementation requires at least five
finite observations for a metric. Cohort selection is metric-specific because
source availability can differ by metric. The dashboard displays both the
eligible candidate count and the usable observation count.

Post-v1 historical peer-cohort distributions, if developed, should use robust
statistics such as median and percentiles rather than relying solely on
arithmetic means.

Reveal v0.6.3 implements cross-sectional metric values at the requested cutoff
using the latest locally stored company classification and eligibility metadata
for cohort membership. This is not a strict historical universe. Annual
selected-security/one-peer history is implemented for the seven frozen metrics.
Five-year and ten-year historical peer-cohort distributions are outside v1
until their point-in-time data contract is implemented and tested.

Relative position does not by itself imply investment quality.

The Financial Profile table summarizes this context on a one-dimensional
percentile axis with ticks at 0, 10, 25, median, 75, 90, and 100 and a marker
for the selected company. The detailed distribution view retains the actual
spread statistics, cohort provenance, interpretation, and selectable chart.

Comparable-security membership uses the same five-tier hierarchy and eligible
common-stock filters. Membership is sourced from persisted company metadata and
returns ticker, company name, industry, sector, and market-cap classification
without calculating financial metrics for every member. A requested tier may
be shown even when its members happen to be identical to a narrower tier. The
membership list represents current locally stored classifications, not a strict
historical universe.

Post-v1 historical peer-cohort distribution research may use robust statistics
such as median, quartiles, percentiles, and IQR. Proposed periods are:

- CURRENT CONDITION: 
  - current cross-sectional distribution

- RECENT NORMAL:
  - 5-year rolling distribution

- LONG-TERM NORMAL:
  - 10-year rolling distribution

There will be some industries that will show different (better/worse) metrics over different periods based on industry cycles,
therefore, having 3 different historical periods will help smooth out, or, at least, provide a more robust view of the security's performance against it's peers over time.
The metric spread within an industry will determine determine how well a company is performing (or not performing) RELATIVE TO ITS PEERS, and not that a company is good or bad because it lies in a certain area of the metrics range.
The company can then be compared to its industry peers, it's market cap group, and the market as a whole.
i.e. how the company has faired against the rest of the industy in relation to their own growth and/or success.


The analysis for each metric shall have the following format for the user:
    
    Metric:                      one of the 7 metrics listed above
    Current value:               14.8%
    Industry distribution:
        90th percentile          22.1%
        75th percentile          16.3%
        Median                    9.8%
        25th percentile           4.9%
        10th percentile           1.7%
        <ticker> percentile:      (ex: 71st, or 29th)
    Interpretation:
        ex: "Above typical industry range", or "Bottom 10 percentile of industry range"


### Defensive Investor Criteria

- The criteria for Defensive Investor is pass/fail. 
- Post-v1 research idea: order Graham-qualified securities by Margin of Safety
  within industry and market-cap groups. This is not a v1 Graham ranking.
- Financial Profile context is separate and is not an ordinal tie-breaker.

1. Annual sales of at least $500 million.
   - Utilities use a minimum of $250 million.
2. Sector-specific financial strength:
   - Industrial and Financial companies use both of these tests:
     - Current assets are at least 2x current liabilities.
     - Long-term debt does not exceed net current assets.
   - Utilities use long-term debt no greater than 2x book equity.
   - These sector-specific tests are marked `not_applicable` for sectors to
     which they do not apply and are excluded from the Defensive summary.
3. Some earnings of the common stock in each of the past 10 years.
4. Uninterrupted common-stock dividend payments for each of the past 20 fiscal
   years, evaluated from fully covered adjusted daily dividend-event history.
   A covered year with no payment fails; incomplete history is unavailable.
5. A minimum increase of at least 1/3 EPS in the past 10 years, using 3 year EPS average for the current EPS, and the average EPS ov year 10, 11, and 12
6. Current share price should not be greater than 15x EPS - considered a moderate price to earnings ratio
    - The number 15 is a general rule, but it is derived from the current AA Corporate Bond rate (Graham used 7.5% which gave 13.3)
    - To determine the appropriate multiple, we can use the current AA Corporate Bond rate as a benchmark:
      - 100 / AA Corporate Bond Rate = multiplier 
      - Example: (100 / 6.66667) = 15
7. Current share price should not be greater than 1.5x Book Value.
    - The price to book value can be proportionately higher to the P/E ratio if it is lower than the general rule of 15
8. Intrinsic Value:
   - Graham Number = (15 * 1.5 * EPS * BVPS)**.5
     - BVPS = Book Value per Share
   - Again, 15 is derivative. Obtain the multiplier, divide it by 15, and multiply that by the Graham Number to adjust for P/E
   - Example: (100 / AA Corporate Bond Rate) / 15 = intrinsic_multiplier
   - Graham Number * intrinsic_multiplier = adjusted_Graham_Number
9. Margin of Safety = Graham Number (or adjusted_Graham_Number if available) / Current Share Price



### Enterprising Investor Criteria
 
- Post-v1 research idea: order Graham-qualified securities by Margin of Safety.
  This is not a v1 Graham ranking.
- Financial Profile context is separate and is not an ordinal tie-breaker.
- Enterprising Investor is also known as an 'aggressive investor'
- Enterprising criteria is a little more 'forgiving' when it comes to a companies leverage and dividend payment


1. Current Assets at least 1.5x current liabilities.
2. Debt not more than 110% of net current assets.
3. Earnings stability: no deficit in the last five years.
4. Dividend record: some current dividend.
5. Earnings growth:last years earnings more than those of 5 years ago.
6. Current share price is not more than 120% net tangible assets.
7. Intrinsic Value:
   - Serenity Number  = (10 * 1.2 * EPS * TBVPS)**.5 
   - TBVPS = Tangible Book Value per Share
   - As with Defensive Investor, 10 is a default multiplier to EPS
   - An intrinsic multiplier is used to adjust for P/E if the current AA corporate bond rate is known/available.
   - intrinsic_multiplier = (100 / AA Corporate Bond Rate) / 10
   - Serenity Number * intrinsic_multiplier = adjusted_Serenity_Number
8. Margin of Safety = Serenity_Number (or adjusted_Serenity_Number if available) / Current Share Price


#### Magic Formula Ranking:

Joel Greenblatt's 'Magic Formula' strategy to investing was taking companies that meet the following criteria, and based the evaluations on 'Return on Capital' (ROC) and 'Earnings Yield' (EY).
The method was explained in his book 'The Little Book That Beats the Market'. 

The implemented ranking calculates ROC and EY, ranks each from highest to
lowest among qualifying securities, sums those ordinal ranks, and orders the
totals from lowest (best) to highest. The selected security's rank is read from
persisted quarterly results; the dashboard's latest-quarter selector is not
recomputed for an optional analysis date.

The current `_eligible_magic_formula_tickers()` filter requires five years of
annual history, at least $100 million in revenue, P/E of at least 5, USD
currency, a U.S. address, and exclusion of the configured financial/utility
sectors and insurance/REIT/utility/investment industries. This filter is
distinct from the broader v1 common-stock analysis preflight. Comparing annual
earnings growth with Treasury yields is a research idea, not an implemented
Magic Formula eligibility rule.


#### Insider Trading (post-v1 research)

- Insider transactions can be obtained from Alphavantage
- For each security, insider transactions are considered part of the financial health of the company.
- Insider's consistently purchasing shares in the company compared to selling shares in the company should be at a ratio of 2.3:1 (selling:buying)
  - Peter Lynch gave this advice in his book "One Up On Wall Street"
  - Insiders sell stock shares for all sorts of reasons, and basing a companies health on insiders selling is speculation.
  - Insiders buy stock shares because they believe the company is going to prosper
- Insider trading is not a ranked metric. It is used to show a user what the people who run the company think of it.

## MISSING VALUES, NULL, AND NEGATIVE VALUES

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

#### Interpreting Criteria States In `mvp.models.SecurityAnalysisResult`

The result contract distinguishes these states:

- VALUE / RESULT
  - passed
  - failed

- NO RESULT
  - unavailable: should apply, cannot evaluate
  - not_applicable: intentionally does not apply

- ELIGIBILITY
  - eligible
  - ineligible
