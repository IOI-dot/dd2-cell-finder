"""Option 2 M2, run with python -m dd2m2. Each step lives in its own module:

    environment   tools and supplied inputs           check
    areamodel     the HD x1 area model                calibrate
    measure       reduced and extended mappings       baseline, measure
    candidates    ranking and cell requests           candidates, requests
    library       the extended Liberty                write_library
    reference     the Table 4 question                witness_report
    report        figures, readiness, TA_M2/          plots, summary, showcase, m1_summary
    pipeline      the whole run                       run

This module keeps the names the command line, the tests and Option 3 use.
"""

from .areamodel import calibrate
from .candidates import candidates, requests
from .environment import check
from .library import write_library
from .measure import baseline, measure
from .pipeline import run
from .reference import witness_report
from .report import m1_summary, plots, showcase, summary
from .tables import write_csv

__all__ = [
    "baseline",
    "calibrate",
    "candidates",
    "check",
    "m1_summary",
    "measure",
    "plots",
    "requests",
    "run",
    "showcase",
    "summary",
    "witness_report",
    "write_csv",
    "write_library",
]
