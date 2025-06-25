# Directory: app/services/scraper_core.py
# This is the main scraper engine, now enhanced with the DynamicQueryBuilder.

import asyncio
import httpx
import functools
from duckduckgo_search import DDGS
from trafilatura import fetch_url, extract
from typing import List, Set, Optional

# Correctly import from your project structure
from app.services.dynamic_query_builder import DynamicQueryBuilder

# --- Configuration ---
REQUEST_TIMEOUT = 10

# This is our "seed" list, which will be expanded upon.
SEED_SEARCH_QUERIES = [
    "best credit card signup bonus offers",
    "limited time credit card offer",
    "best credit card offers flyertalk",
    "new credit card bonus reddit churning",
    "doctor of credit best card bonuses",
    "high yield savings account bonus 2024",
    "brokerage account opening bonus",
]

# Domains to exclude from search results
EXCLUDED_DOMAINS = [
    "google.com", "youtube.com", "facebook.com", "twitter.com",
    "linkedin.com", "instagram.com", "pinterest.com", "duckduckgo.com"
]

# Failsafe URLs if search fails
FAILSAFE_URLS = [
    "https://www.doctorofcredit.com/best-credit-card-sign-up-bonuses/",
    "https://www.flyertalk.com/forum/credit-card-programs-599/",
    "https://www.nerdwallet.com/best/credit-cards/sign-up-bonus",
]

# --- Mock AI Analysis Function ---
class MockOpportunity:
    def __init__(self, title: str, trust_score: int, source_url: str, summary: str = ""):
        self.title = title
        self.trust_score = trust_score
        self.source_url = source_url
        self.summary = summary

def analyze_opportunity_with_ai(text_content: str, source_url: str) -> Optional[MockOpportunity]:
    print(f"🤖 AI: Analyzing content from: {source_url}")
    text_lower = text_content.lower()
    high_confidence_keywords = [
        "bonus", "grant", "rebate", "scholarship", "claim", "settlement", "unclaimed",
        "sign-up bonus", "welcome offer", "statement credit", "annual fee waived",
        "companion pass", "lounge access"
    ]
    if any(keyword in text_lower for keyword in high_confidence_keywords):
        print("  - ✅ AI: High-confidence keyword found.")
        return MockOpportunity(title="Potential Financial Opportunity Found", trust_score=7, source_url=source_url)
    elif len(text_content) > 500:
         print("  - ⚠️ AI: No high-confidence keywords, substantial content.")
         return MockOpportunity(title="Low-Confidence Opportunity", trust_score=3, source_url=source_url)
    print(f"  - ❌ AI: Content from {source_url} is too short or irrelevant.")
    return None

# --- Core Scraper Class ---
class ScraperCore:
    def __init__(self, search_queries: List[str]):
        self.search_queries = search_queries

    def _is_valid_link(self, url: str) -> bool:
        if not url or not url.startswith("http"): return False
        try:
            domain = url.split("://")[1].split("/")[0]
            if any(excluded in domain for excluded in EXCLUDED_DOMAINS): return False
        except IndexError: return False
        return True

    async def discover_urls(self) -> Set[str]:
        all_links = set()
        print("🌱 Starting URL discovery using expanded query list...")
        try:
            with DDGS() as ddgs:
                for query in self.search_queries:
                    print(f"  -> Searching for: '{query}'")
                    results = list(ddgs.text(query, max_results=5))
                    if not results: continue
                    for result in results:
                        url = result.get('href')
                        if self._is_valid_link(url):
                            all_links.add(url)
        except Exception as e:
            print(f"❗️❗️ An error during DuckDuckGo search: {e}")

        if not all_links:
            print("\n⚠️ Live search failed. Switching to failsafe URLs.\n")
            return set(FAILSAFE_URLS)
        
        print(f"🌱 Discovered {len(all_links)} unique URLs from {len(self.search_queries)} queries.\n")
        return all_links

    async def process_links(self, urls: Set[str]) -> List[MockOpportunity]:
        tasks = [self._fetch_and_analyze(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return [result for result in results if result]

    async def _fetch_and_analyze(self, url: str) -> Optional[MockOpportunity]:
        try:
            print(f"📰 Fetching: {url}")
            loop = asyncio.get_running_loop()
            fetch_with_timeout = functools.partial(fetch_url, url, timeout=REQUEST_TIMEOUT)
            downloaded = await loop.run_in_executor(None, fetch_with_timeout)
            if not downloaded:
                print(f"  - ❗️ Fetch failed for {url} (timed out or blocked).")
                return None
            text_content = extract(downloaded, include_comments=False, include_tables=False)
            if not text_content:
                print(f"  - ❗️ Could not extract main content from {url}.")
                return None
            return analyze_opportunity_with_ai(text_content, source_url=url)
        except Exception as e:
            print(f"  - ❗️❗️ Unexpected error processing {url}: {e}")
            return None

# --- Main Execution Logic ---
async def main():
    print("--- SCRIPT STARTED: SELF-EXPANDING MODE ---")
    
    query_builder = DynamicQueryBuilder(SEED_SEARCH_QUERIES)
    dynamic_queries = await query_builder.expand_queries()
    
    scraper = ScraperCore(dynamic_queries)
    
    urls_to_scan = await scraper.discover_urls()
    if not urls_to_scan:
        print("🛑 CRITICAL ERROR: No URLs to scan. Cannot proceed.")
        return

    print(f"🕵️ Processing {len(urls_to_scan)} URLs through the AI filter...")
    all_opportunities = await scraper.process_links(urls_to_scan)
    
    final_opportunities = [opp for opp in all_opportunities if opp.trust_score >= 5]
    print(f"✅ Found {len(final_opportunities)} valid opportunities with trust score >= 5:\n")

    if final_opportunities:
        final_opportunities.sort(key=lambda x: x.trust_score, reverse=True)
        output_lines = [f"- {opp.title} ({opp.trust_score}/10)\n  Source: {opp.source_url}\n" for opp in final_opportunities]
        for line in output_lines:
            print(line)
        with open("financial_opportunities.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        print("\n📄 Results saved to financial_opportunities.txt")
    else:
        print("  - No pages met the final trust score threshold of 5.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"💥 An unexpected error occurred at the top level: {e}")
    finally:
        print("--- SCRIPT FINISHED ---")

