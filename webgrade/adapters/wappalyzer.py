from __future__ import annotations

import re
from typing import Any

import httpx


GENERATOR_PATTERNS = [
    (re.compile(r"wordpress(?:\s+([0-9][0-9A-Za-z.\-]+))?", re.I), "WordPress"),
    (re.compile(r"drupal(?:\s+([0-9][0-9A-Za-z.\-]+))?", re.I), "Drupal"),
    (re.compile(r"joomla!?[\s/]*([0-9][0-9A-Za-z.\-]+)?", re.I), "Joomla"),
    (re.compile(r"typo3(?:\s+cms)?(?:\s+([0-9][0-9A-Za-z.\-]+))?", re.I), "TYPO3"),
    (re.compile(r"sitefinity(?:\s+([0-9][0-9A-Za-z.\-]+))?", re.I), "Sitefinity"),
    (re.compile(r"squarespace", re.I), "Squarespace"),
    (re.compile(r"wix\.com", re.I), "Wix"),
]

FRAMEWORK_PATTERNS = {
    "jQuery": re.compile(r"jquery(?:[-.][0-9.]+)?(?:\.min)?\.js|window\.jQuery", re.I),
    "Bootstrap": re.compile(r"bootstrap(?:[-.][0-9.]+)?(?:\.min)?\.(?:css|js)|class=[\"'][^\"']*\bnavbar\b", re.I),
    "React": re.compile(r"__NEXT_DATA__|data-reactroot|react(?:[-.][0-9.]+)?(?:\.min)?\.js", re.I),
    "Vue": re.compile(r"vue(?:[-.][0-9.]+)?(?:\.min)?\.js|data-v-[0-9a-f]{6,}", re.I),
    "Angular": re.compile(r"ng-version=|angular(?:[-.][0-9.]+)?(?:\.min)?\.js", re.I),
}

ANALYTICS_PATTERNS = {
    "Google Analytics": re.compile(r"google-analytics\.com|gtag\(|ga\(", re.I),
    "Google Tag Manager": re.compile(r"googletagmanager\.com", re.I),
    "Matomo": re.compile(r"matomo\.js|piwik\.js", re.I),
    "Adobe Analytics": re.compile(r"omtrdc\.net|s_code\.js|adobe analytics", re.I),
    "Hotjar": re.compile(r"hotjar", re.I),
}

ACCESSIBILITY_TOOLBAR_PATTERNS = [
    re.compile(r"userway|uayWidget", re.I),
    re.compile(r"accessibe", re.I),
    re.compile(r"audioeye", re.I),
    re.compile(r"reciteme", re.I),
]

STATIC_STACK_PATTERNS = [
    (re.compile(r"generator[\"'][^>]*content=[\"'][^\"']*hugo", re.I), "Hugo"),
    (re.compile(r"generator[\"'][^>]*content=[\"'][^\"']*jekyll", re.I), "Jekyll"),
    (re.compile(r"gatsby", re.I), "Gatsby"),
    (re.compile(r"__NEXT_DATA__", re.I), "Next.js"),
]


def _extract_generator(html: str) -> str | None:
    match = re.search(
        r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']([^\"']+)[\"']",
        html,
        flags=re.I,
    )
    return match.group(1).strip() if match else None


def _parse_cms(generator: str | None, html: str) -> tuple[str | None, str | None]:
    text = " ".join(part for part in [generator, html] if part)
    for pattern, cms_name in GENERATOR_PATTERNS:
        match = pattern.search(text)
        if match:
            version = match.group(1) if match.lastindex else None
            return cms_name, version

    if re.search(r"wp-content|wp-includes|/xmlrpc\.php", html, re.I):
        return "WordPress", None
    if re.search(r"drupalSettings|/sites/default/|Drupal\.behaviors", html, re.I):
        return "Drupal", None
    if re.search(r"joomla!|/media/system/js/|option=com_", html, re.I):
        return "Joomla", None
    return None, None


def _detect_frameworks(html: str) -> list[str]:
    return [name for name, pattern in FRAMEWORK_PATTERNS.items() if pattern.search(html)]


def _detect_analytics(html: str) -> list[str]:
    return [name for name, pattern in ANALYTICS_PATTERNS.items() if pattern.search(html)]


def _detect_hosting_provider(headers: httpx.Headers) -> str | None:
    server = " ".join(
        [
            headers.get("server", ""),
            headers.get("x-powered-by", ""),
            headers.get("via", ""),
        ]
    ).lower()
    if "cloudflare" in server or headers.get("cf-cache-status"):
        return "Cloudflare"
    if headers.get("x-vercel-cache"):
        return "Vercel"
    if headers.get("x-nf-request-id"):
        return "Netlify"
    if "azure" in server:
        return "Azure"
    if "amazon" in server or "cloudfront" in server:
        return "AWS"
    return None


def _has_accessibility_toolbar(html: str) -> bool:
    return any(pattern.search(html) for pattern in ACCESSIBILITY_TOOLBAR_PATTERNS)


def _major_version(version: str | None) -> int | None:
    if not version:
        return None
    match = re.match(r"(\d+)", version)
    return int(match.group(1)) if match else None


def _platform_status(cms_name: str | None, cms_version: str | None, html: str) -> str:
    if cms_name is None:
        for pattern, _stack_name in STATIC_STACK_PATTERNS:
            if pattern.search(html):
                return "modern_static"
        return "unknown"

    major = _major_version(cms_version)
    if cms_name == "WordPress":
        if major is None:
            return "unknown_version"
        if major >= 6:
            return "supported_current"
        if major == 5:
            return "supported_old"
        return "nearing_eol"
    if cms_name == "Drupal":
        if major is None:
            return "unknown_version"
        if major >= 10:
            return "supported_current"
        if major == 9:
            return "supported_old"
        if major == 8:
            return "nearing_eol"
        return "eol"
    if cms_name == "Joomla":
        if major is None:
            return "unknown_version"
        if major >= 5:
            return "supported_current"
        if major == 4:
            return "supported_old"
        return "eol"
    if cms_name in {"TYPO3", "Sitefinity", "Squarespace", "Wix"}:
        return "unknown_version" if cms_version is None else "supported_current"
    return "unknown"


def inspect_technologies(html: str, headers: httpx.Headers) -> dict[str, Any]:
    generator = _extract_generator(html)
    cms_name, cms_version = _parse_cms(generator, html)
    frameworks = _detect_frameworks(html)
    analytics_tools = _detect_analytics(html)
    hosting_provider = _detect_hosting_provider(headers)
    return {
        "cms_name": cms_name,
        "cms_version": cms_version,
        "platform_status": _platform_status(cms_name, cms_version, html),
        "frameworks": frameworks,
        "hosting_provider": hosting_provider,
        "analytics_tools": analytics_tools,
        "has_accessibility_toolbar": _has_accessibility_toolbar(html),
        "generator": generator,
    }


def run_wappalyzer(url: str, client: httpx.Client | None = None) -> dict[str, Any]:
    owns_client = client is None
    client = client or httpx.Client(timeout=20.0, follow_redirects=True)
    try:
        response = client.get(url)
        response.raise_for_status()
        summary = inspect_technologies(response.text, response.headers)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Technology inspection failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    return {
        "adapter_key": "wappalyzer",
        "viewport": "combined",
        "status": "ok",
        "summary": {
            "cms_name": summary["cms_name"],
            "cms_version": summary["cms_version"],
            "platform_status": summary["platform_status"],
            "frameworks": summary["frameworks"],
            "hosting_provider": summary["hosting_provider"],
            "analytics_tools": summary["analytics_tools"],
            "has_accessibility_toolbar": summary["has_accessibility_toolbar"],
        },
        "raw": {
            "generator": summary["generator"],
            "headers": dict(response.headers),
        },
        "error": None,
    }
