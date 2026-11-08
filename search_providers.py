import json
import re
from urllib.parse import urlencode, urlsplit


ENGINES = (
    "Google",
    "Brave",
    "DuckDuckGo",
    "Bing",
    "Ecosia",
    "Qwant",
    "Yahoo",
    "Startpage",
)

LANGUAGES = {
    "Français": ("fr", "FR"),
    "English": ("en", "US"),
    "Español": ("es", "ES"),
    "Deutsch": ("de", "DE"),
    "Italiano": ("it", "IT"),
    "Português": ("pt", "BR"),
    "Nederlands": ("nl", "NL"),
    "العربية": ("ar", "SA"),
    "中文": ("zh", "CN"),
}

_STARTPAGE_LANGUAGES = {
    "fr": "francais",
    "en": "english",
    "es": "espanol_es",
    "de": "deutsch",
    "it": "italiano",
    "pt": "portugues",
    "nl": "nederlands",
}

_DUCKDUCKGO_REGIONS = {
    "fr": "fr-fr",
    "en": "us-en",
    "es": "es-es",
    "de": "de-de",
    "it": "it-it",
    "pt": "br-pt",
    "nl": "nl-nl",
    "ar": "xa-ar",
    "zh": "cn-zh",
}


def build_search_url(
    query: str, engine: str = "Google", language: str = "fr"
) -> str:
    """Build a provider search URL using the selected query language."""
    query = query.strip()
    if not query:
        raise ValueError("Saisissez quelques mots à rechercher.")
    if engine not in ENGINES:
        raise ValueError(f"Moteur de recherche non pris en charge : {engine}")

    locale, country = LANGUAGES.get(language, LANGUAGES["Français"])
    if language in {code for code, _region in LANGUAGES.values()}:
        locale = language
        country = next(
            region for code, region in LANGUAGES.values() if code == language
        )
    encoded_query = urlencode({"q": query})
    encoded_country = country.upper()

    if engine == "Google":
        return "https://www.google.com/search?" + urlencode(
            {"q": query, "hl": locale, "gl": country}
        )
    if engine == "Brave":
        return "https://search.brave.com/search?" + urlencode(
            {"q": query, "source": "web", "country": country.lower()}
        )
    if engine == "DuckDuckGo":
        region = _DUCKDUCKGO_REGIONS.get(locale, "wt-wt")
        return f"https://html.duckduckgo.com/html/?{encoded_query}&kl={region}"
    if engine == "Bing":
        return (
            "https://www.bing.com/search?"
            + urlencode(
                {"q": query, "setlang": locale, "cc": encoded_country}
            )
        )
    if engine == "Ecosia":
        return (
            "https://www.ecosia.org/search?"
            + urlencode({"q": query, "lang": locale})
        )
    if engine == "Qwant":
        return (
            "https://www.qwant.com/?"
            + urlencode(
                {"q": query, "t": "web", "locale": f"{locale}_{country}"}
            )
        )
    if engine == "Yahoo":
        return (
            "https://search.yahoo.com/search?"
            + urlencode({"p": query, "ei": "UTF-8", "fr": country.lower()})
        )
    return (
        "https://www.startpage.com/sp/search?"
        + urlencode(
            {
                "query": query,
                "language": _STARTPAGE_LANGUAGES.get(locale, "english"),
            }
        )
    )


def is_web_address(text: str) -> bool:
    """Return whether the entered string is an HTTP(S) URL or a domain name."""
    value = text.strip()
    if not value:
        return False
    if re.match(r"^https?://", value, re.IGNORECASE):
        try:
            parsed = urlsplit(value)
            parsed.port
        except ValueError:
            return False
        return bool(parsed.hostname)
    if value.startswith("//"):
        return True
    return bool(
        re.fullmatch(
            r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
            r"[a-zA-Z]{2,}(?::\d+)?(?:[/?#].*)?",
            value,
        )
    )


def build_result_script(engine: str) -> str:
    """Build a small DOM extractor for the selected public search page."""
    selectors = {
        "Google": "h3",
        "Brave": "a.l1",
        "DuckDuckGo": 'a[data-testid="result-title-a"], a.result__a',
        "Bing": "li.b_algo h2 a, h2 a",
        "Ecosia": 'a.result-title, a[data-test-id="result-link"]',
        "Qwant": (
            'a[href^="http"]:has(h2), a[href^="http"]:has(h3), '
            'a[data-testid="result-title"]'
        ),
        "Yahoo": "div.algo h3 a, h3 a",
        "Startpage": "a.w-gl__result-title",
    }
    selector = selectors.get(engine, "a.l1")
    return f"""
(() => {{
  const selector = {json.dumps(selector)};
  const selectedEngine = {json.dumps(engine)};
  let candidates = [];
  try {{ candidates = [...document.querySelectorAll(selector)]; }} catch (_) {{}}
  if (!candidates.length) {{
    candidates = [...document.querySelectorAll('a[href^="http"]')]
      .filter(link => link.querySelector('h2, h3'));
  }}
  const seen = new Set();
  const results = [];
  for (const candidate of candidates) {{
    const link = candidate.matches('a') ? candidate : candidate.closest('a');
    if (!link || !link.href) continue;
    let url = link.href;
    try {{
      const parsed = new URL(url);
      if (parsed.hostname.endsWith('google.com') && parsed.pathname === '/url') {{
        url = parsed.searchParams.get('url') || parsed.searchParams.get('q') || url;
      }}
      const destination = new URL(url);
      if (!['http:', 'https:'].includes(destination.protocol)) continue;
      const host = destination.hostname.toLowerCase();
      const searchHosts = ['google.com', 'brave.com', 'bing.com',
        'duckduckgo.com', 'ecosia.org', 'qwant.com', 'yahoo.com',
        'startpage.com'];
      if (searchHosts.some(domain => host === domain
          || host.endsWith('.' + domain))) continue;
    }} catch (_) {{ continue; }}
    const heading = link.querySelector('h1, h2, h3')
      || (candidate.matches('h1,h2,h3') ? candidate : null);
    const linkLines = (link.innerText || '').split('\\n')
      .map(line => line.trim()).filter(Boolean);
    const title = (heading ? heading.innerText
      : selectedEngine === 'Brave' ? linkLines[linkLines.length - 1]
      : linkLines[0] || '').trim().split('\\n')[0].trim();
    if (!title || seen.has(url) || title.length < 3) continue;
    seen.add(url);
    const card = link.closest('li') || link.closest('[class*="result"]')
      || link.parentElement?.parentElement;
    const text = card ? (card.innerText || '') : (link.innerText || '');
    const sourceLines = selectedEngine === 'Brave' ? linkLines.slice(0, 2) : [];
    const snippet = text.trim().split('\\n')
      .map(line => line.trim())
      .filter(line => line && line !== title && !line.startsWith('http'))
      .filter(line => !sourceLines.includes(line))
      .filter(line => !line.includes('›'))
      .slice(0, 3).join(' ');
    results.push({{title, url, snippet}});
    if (results.length >= 20) break;
  }}
  return JSON.stringify(results);
}})()
"""


def parse_search_results(items):
    results = []
    seen_urls = set()

    if not isinstance(items, list):
        return results

    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "")
        raw_title = item.get("title", "")
        if not isinstance(url, str) or not isinstance(raw_title, str):
            continue
        title_lines = [
            line.strip()
            for line in raw_title.splitlines()
            if line.strip()
        ]
        if not title_lines:
            continue
        try:
            parsed = urlsplit(url)
            parsed.port
        except (TypeError, ValueError):
            continue
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or url in seen_urls
        ):
            continue

        title = title_lines[0]
        raw_snippet = item.get("snippet", "")
        if isinstance(raw_snippet, str):
            snippet = " ".join(
                line.strip()
                for line in raw_snippet.splitlines()
                if line.strip() and "›" not in line
            )
        else:
            snippet = ""
        if not snippet:
            description_lines = [
                line
                for line in title_lines[1:]
                if "›" not in line
                and not re.fullmatch(
                    r"(?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}/?",
                    line,
                )
            ]
            snippet = " ".join(description_lines)
        results.append((title, url, snippet))
        seen_urls.add(url)

    return results
