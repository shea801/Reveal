import pytest

from analytics import MyMagicFormula as magic_formula


EXPECTED_COLUMNS = [
    "ticker",
    "quarter_date",
    "associated_annual_date",
    "magic_formula_rank",
    "return_on_capital_rank",
    "earnings_yield_rank",
    "total_roc_ey_score",
]


def _install_fake_assessment(monkeypatch, rows, failures=None):
    failures = set(failures or [])
    calls = []

    class FakeFinancialAssessment:
        def __init__(self, ticker, date=None):
            calls.append((ticker, date))
            if ticker in failures:
                raise RuntimeError("synthetic assessment failure")
            self.ticker = ticker
            self.date = date

        def magic_formula_values(self):
            row = rows[self.ticker]
            return {
                "ticker": self.ticker,
                "quarter_date": row.get("quarter_date", self.date),
                "associated_annual_date": row.get(
                    "associated_annual_date", "2023-12-31"
                ),
                "return_on_capital": row.get("return_on_capital"),
                "earnings_yield": row.get("earnings_yield"),
            }

    monkeypatch.setattr(magic_formula, "FA", FakeFinancialAssessment)
    return calls


def test_magic_formula_ranked_securities_returns_empty_frame_for_empty_universe(
    monkeypatch,
):
    monkeypatch.setattr(magic_formula, "_eligible_magic_formula_tickers", lambda: [])

    result = magic_formula.magic_formula_ranked_securities()

    assert result.empty
    assert list(result.columns) == EXPECTED_COLUMNS


def test_magic_formula_ranked_securities_returns_empty_frame_for_invalid_date(
    monkeypatch,
):
    monkeypatch.setattr(
        magic_formula,
        "has_minimum_annual_history",
        lambda ticker, years: pytest.fail("history should not be checked"),
    )

    result = magic_formula.magic_formula_ranked_securities(
        tickers_list=["AAPL"],
        date="not-a-date",
    )

    assert result.empty
    assert list(result.columns) == EXPECTED_COLUMNS


def test_magic_formula_ranked_securities_uses_explicit_ticker_list(monkeypatch):
    monkeypatch.setattr(
        magic_formula,
        "_eligible_magic_formula_tickers",
        lambda: pytest.fail("default ticker universe should not be loaded"),
    )
    monkeypatch.setattr(
        magic_formula,
        "has_minimum_annual_history",
        lambda ticker, years: True,
    )
    calls = _install_fake_assessment(
        monkeypatch,
        {
            "AAPL": {
                "quarter_date": "2024-12-31",
                "associated_annual_date": "2023-12-31",
                "return_on_capital": 0.12,
                "earnings_yield": 0.03,
            }
        },
    )

    result = magic_formula.magic_formula_ranked_securities(
        tickers_list=["AAPL"],
        date="2024-12-31",
    )

    assert calls == [("AAPL", "2024-12-31")]
    assert result.iloc[0].to_dict() == {
        "ticker": "AAPL",
        "quarter_date": "2024-12-31",
        "associated_annual_date": "2023-12-31",
        "magic_formula_rank": 1,
        "return_on_capital_rank": 1,
        "earnings_yield_rank": 1,
        "total_roc_ey_score": 2,
    }


def test_magic_formula_ranked_securities_skips_unrankable_and_failed_tickers(
    monkeypatch,
):
    monkeypatch.setattr(
        magic_formula,
        "has_minimum_annual_history",
        lambda ticker, years: ticker != "SKIP",
    )
    calls = _install_fake_assessment(
        monkeypatch,
        {
            "GOOD": {"return_on_capital": 0.2, "earnings_yield": 0.1},
            "MISSING": {"return_on_capital": None, "earnings_yield": 0.1},
        },
        failures={"FAIL"},
    )

    result = magic_formula.magic_formula_ranked_securities(
        tickers_list=["GOOD", "SKIP", "FAIL", "MISSING"],
        date="2024-12-31",
    )

    assert calls == [
        ("FAIL", "2024-12-31"),
        ("GOOD", "2024-12-31"),
        ("MISSING", "2024-12-31"),
    ]
    assert result["ticker"].tolist() == ["GOOD"]


def test_magic_formula_ranked_securities_ranks_roc_and_ey_independently(
    monkeypatch,
):
    monkeypatch.setattr(
        magic_formula,
        "has_minimum_annual_history",
        lambda ticker, years: True,
    )
    _install_fake_assessment(
        monkeypatch,
        {
            "AAA": {"return_on_capital": 0.30, "earnings_yield": 0.02},
            "BBB": {"return_on_capital": 0.20, "earnings_yield": 0.10},
            "CCC": {"return_on_capital": 0.10, "earnings_yield": 0.05},
        },
    )

    result = magic_formula.magic_formula_ranked_securities(
        tickers_list=["CCC", "AAA", "BBB"],
        date="2024-12-31",
    )

    assert result.to_dict(orient="records") == [
        {
            "ticker": "BBB",
            "quarter_date": "2024-12-31",
            "associated_annual_date": "2023-12-31",
            "magic_formula_rank": 1,
            "return_on_capital_rank": 2,
            "earnings_yield_rank": 1,
            "total_roc_ey_score": 3,
        },
        {
            "ticker": "AAA",
            "quarter_date": "2024-12-31",
            "associated_annual_date": "2023-12-31",
            "magic_formula_rank": 2,
            "return_on_capital_rank": 1,
            "earnings_yield_rank": 3,
            "total_roc_ey_score": 4,
        },
        {
            "ticker": "CCC",
            "quarter_date": "2024-12-31",
            "associated_annual_date": "2023-12-31",
            "magic_formula_rank": 3,
            "return_on_capital_rank": 3,
            "earnings_yield_rank": 2,
            "total_roc_ey_score": 5,
        },
    ]


def test_magic_formula_ranked_securities_breaks_metric_ties_by_ticker(
    monkeypatch,
):
    monkeypatch.setattr(
        magic_formula,
        "has_minimum_annual_history",
        lambda ticker, years: True,
    )
    _install_fake_assessment(
        monkeypatch,
        {
            "AAA": {"return_on_capital": 0.2, "earnings_yield": 0.1},
            "BBB": {"return_on_capital": 0.2, "earnings_yield": 0.1},
        },
    )

    result = magic_formula.magic_formula_ranked_securities(
        tickers_list=["BBB", "AAA"],
        date="2024-12-31",
    )

    assert result["ticker"].tolist() == ["AAA", "BBB"]
    assert result["magic_formula_rank"].tolist() == [1, 2]
    assert result["return_on_capital_rank"].tolist() == [1, 2]
    assert result["earnings_yield_rank"].tolist() == [1, 2]
