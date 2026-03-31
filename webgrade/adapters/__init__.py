from webgrade.adapters.accessibility import run_pa11y
from webgrade.adapters.dom import run_dom_heuristics
from webgrade.adapters.freshness import run_freshness
from webgrade.adapters.pagespeed import run_pagespeed
from webgrade.adapters.screenshots import capture_screenshots
from webgrade.adapters.security import run_security_headers, run_tls_certificate
from webgrade.adapters.vision import run_vision_for_captures
from webgrade.adapters.wappalyzer import run_wappalyzer

__all__ = [
    "capture_screenshots",
    "run_dom_heuristics",
    "run_freshness",
    "run_pa11y",
    "run_pagespeed",
    "run_security_headers",
    "run_tls_certificate",
    "run_vision_for_captures",
    "run_wappalyzer",
]
