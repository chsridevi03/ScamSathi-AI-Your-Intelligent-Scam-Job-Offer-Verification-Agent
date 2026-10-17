"""
Evidence-based web research service using Tavily Search API.
Prioritizes official domains, recruitment guidelines, and verified public records.
Enforces SSRF prevention and URL validation.
"""

import re
import urllib.parse
from typing import List, Dict, Any, Optional
import requests
from config import settings

# Private IP and malicious destination ranges
PRIVATE_NETWORK_PATTERNS = [
    re.compile(r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?(/.*)?$", re.IGNORECASE),
    re.compile(r"^https?://(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?(/.*)?$", re.IGNORECASE),
    re.compile(r"^https?://169\.254\.\d{1,3}\.\d{1,3}(:\d+)?(/.*)?$", re.IGNORECASE),
]

OFFICIAL_DOMAINS_WHITELIST_SUFFIXES = [
    ".gov.in", ".nic.in", ".ac.in", ".edu.in", ".gov", ".edu", ".org",
    "careers.google.com", "google.com", "microsoft.com", "amazon.jobs",
    "tcs.com", "infosys.com", "wipro.com", "accenture.com", "internshala.com"
]

def is_safe_public_url(url: str) -> bool:
    """Validate that URL is http/https and not pointing to local/private network addresses."""
    if not url or not isinstance(url, str):
        return False
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    if not hostname:
        return False
    for pattern in PRIVATE_NETWORK_PATTERNS:
        if pattern.match(url.strip()):
            return False
    return True

def is_official_evidence_source(url: str) -> bool:
    """Determine if a URL belongs to a high-trust official public registry or verified careers portal."""
    if not url:
        return False
    hostname = urllib.parse.urlparse(url).hostname or ""
    hostname = hostname.lower()
    return any(hostname.endswith(sfx) or hostname == sfx for sfx in OFFICIAL_DOMAINS_WHITELIST_SUFFIXES)

class SearchService:
    """Tavily search client with security filtering and official source classification."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"

    def search_evidence(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Execute real-time web search for evidence regarding claims.
        Returns a list of structured source dictionaries.
        """
        if not query or len(query.strip()) < 3:
            return []

        # If Tavily API Key is not provided, return structured indicator
        if not self.api_key:
            return [
                {
                    "title": "Tavily Search API Key Not Configured",
                    "url": "https://tavily.com",
                    "content": "To enable live web evidence retrieval, provide TAVILY_API_KEY in your environment or hosting secrets. ScamSathi AI will then fetch real-time public records, recruitment alerts, and domain verification data.",
                    "score": 0.0,
                    "is_official": False,
                    "published_date": None
                }
            ]

        try:
            payload = {
                "api_key": self.api_key,
                "query": query.strip(),
                "search_depth": "advanced",
                "include_answer": True,
                "max_results": min(max_results, settings.MAX_SEARCH_RESULTS),
                "include_raw_content": False
            }

            resp = requests.post(
                self.base_url,
                json=payload,
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
                headers={"Content-Type": "application/json", "User-Agent": "ScamSathiAI-Agent/1.0"}
            )
            
            if resp.status_code != 200:
                return [{
                    "title": f"Tavily Search HTTP {resp.status_code}",
                    "url": "https://tavily.com",
                    "content": f"Search request returned status code {resp.status_code}: {resp.text[:200]}",
                    "score": 0.0,
                    "is_official": False,
                    "published_date": None
                }]

            data = resp.json()
            raw_results = data.get("results", [])
            evidence: List[Dict[str, Any]] = []

            for item in raw_results:
                link = item.get("url", "")
                if not is_safe_public_url(link):
                    continue

                evidence.append({
                    "title": item.get("title", "Web Source"),
                    "url": link,
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0),
                    "is_official": is_official_evidence_source(link),
                    "published_date": item.get("published_date")
                })

            return evidence

        except Exception as e:
            return [{
                "title": "Search Request Exception",
                "url": "https://status.tavily.com",
                "content": f"Encountered network error during search: {str(e)}",
                "score": 0.0,
                "is_official": False,
                "published_date": None
            }]
