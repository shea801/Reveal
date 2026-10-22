from dashboard.app import _magic_formula_dropdown_options, create_app
from mvp.models import MagicFormulaRankedSecurity, SecurityAnalysisResult
from mvp.service import current_magic_formula_ranked_securities


def _rankings():
    return (
        MagicFormulaRankedSecurity(
            rank=1,
            ticker="ALFA",
            company_name="Alpha Industries",
            quarter_date="2026-06-30",
        ),
        MagicFormulaRankedSecurity(
            rank=2,
            ticker="BETA",
            company_name="Beta Holdings",
            quarter_date="2026-06-30",
        ),
    )


def _find_component(component, component_id):
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    if not isinstance(children, (list, tuple)):
        children = [children] if children is not None else []
    for child in children:
        found = _find_component(child, component_id)
        if found is not None:
            return found
    return None


def test_current_magic_formula_rankings_are_sorted_and_named_from_providers():
    rows = (
        {
            "ticker": "beta",
            "quarter_date": "2026-06-30",
            "magic_formula_rank": 2,
        },
        {
            "ticker": "alfa",
            "quarter_date": "2026-06-30",
            "magic_formula_rank": 1,
        },
    )

    result = current_magic_formula_ranked_securities(
        rankings_provider=lambda: rows,
        company_name_provider=lambda tickers: {
            "ALFA": "Alpha Industries",
            "BETA": "Beta Holdings",
        },
    )

    assert [(item.rank, item.ticker, item.company_name) for item in result] == [
        (1, "ALFA", "Alpha Industries"),
        (2, "BETA", "Beta Holdings"),
    ]
    assert {item.quarter_date for item in result} == {"2026-06-30"}


def test_magic_formula_dropdown_labels_show_rank_ticker_and_company_name():
    assert _magic_formula_dropdown_options(_rankings()) == [
        {"label": "1. ALFA | Alpha Industries", "value": "ALFA"},
        {"label": "2. BETA | Beta Holdings", "value": "BETA"},
    ]


def test_dashboard_places_magic_formula_dropdown_after_date_selector():
    app = create_app(
        analyzer=lambda ticker, analysis_date: SecurityAnalysisResult(
            ticker=ticker,
            company_name="Test Company",
            analysis_date=analysis_date,
        ),
        magic_formula_rankings_provider=_rankings,
    )
    controls = _find_component(app.layout, "magic-formula-security-select")

    assert controls is not None
    assert controls.disabled is False
    assert controls.placeholder == "Select from 2026-06-30 rankings"
    assert controls.options == _magic_formula_dropdown_options(_rankings())
    assert any(
        "ticker-input.value" in output for output in app.callback_map
    )


def test_dashboard_disables_magic_formula_dropdown_when_rankings_unavailable():
    app = create_app(
        analyzer=lambda ticker, analysis_date: SecurityAnalysisResult(
            ticker=ticker,
            company_name="Test Company",
            analysis_date=analysis_date,
        ),
        magic_formula_rankings_provider=lambda: (),
    )
    dropdown = _find_component(app.layout, "magic-formula-security-select")

    assert dropdown.disabled is True
    assert dropdown.options == []
    assert dropdown.placeholder == "Rankings unavailable"
