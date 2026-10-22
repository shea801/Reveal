"""Compatibility imports for the Reveal application analysis package.

New code should import from ``mvp.service`` or ``mvp.models`` directly. This
module remains so existing notebooks and older scripts can keep using the
historical ``minimum_viable_product`` import path during the package migration.
"""

from mvp.models import SecurityAnalysisResult
from mvp.service import (
    DEFENSIVE_CRITERIA_MAP,
    DEFENSIVE_GRAHAM_MAP,
    ENTERPRISING_CRITERIA_MAP,
    ENTERPRISING_GRAHAM_MAP,
    FINANCIAL_ASSESSMENT_MAP,
    analyze_security,
    apply_map,
    build_security_analysis_result,
    eligible_common_stock_analysis,
    eligible_common_stock_tickers,
)

__all__ = [
    "DEFENSIVE_CRITERIA_MAP",
    "DEFENSIVE_GRAHAM_MAP",
    "ENTERPRISING_CRITERIA_MAP",
    "ENTERPRISING_GRAHAM_MAP",
    "FINANCIAL_ASSESSMENT_MAP",
    "SecurityAnalysisResult",
    "analyze_security",
    "apply_map",
    "build_security_analysis_result",
    "eligible_common_stock_analysis",
    "eligible_common_stock_tickers",
]
