# Directory: app/services/scraper_core.py
# IMPORTANT: To run this file, navigate to the project's root directory (Free-Money/)
# and use the command: python -m app.services.scraper_core
# FIRST TIME SETUP: run `pip install playwright` and then `playwright install`

import asyncio
import random
from duckduckgo_search import DDGS
from trafilatura import extract
from typing import List, Set, Optional
from playwright.async_api import async_playwright

# --- Configuration ---

# Comprehensive list of search queries.
SEARCH_QUERIES = [
    # Core Credit Card Queries
    "best credit card signup bonus offers",
    "limited time credit card offer",
    "best credit cards for travel points",
    "no annual fee credit card bonus",
    "best cash back credit cards",

    # Community & Forum Queries - Where the best deals surface first
    "best credit card offers flyertalk",
    "new credit card bonus reddit churning",
    "doctor of credit best card bonuses",
    "bogleheads credit card recommendations",

    # Broader Financial Queries
    "best high yield savings account bonus",
    "brokerage account opening bonus",
    "best bank account promotions",
]

# Domains to exclude from search results
EXCLUDED_DOMAINS = [
    "google.com", "youtube.com", "facebook.com", "twitter.com",
    "linkedin.com", "instagram.com", "pinterest.com", "duckduckgo.com"
]

# Failsafe URLs if all web searches fail
FAILSAFE_URLS = [
    "https://www.doctorofcredit.com/best-credit-card-sign-up-bonuses/",
    "https://www.flyertalk.com/forum/credit-card-programs-599/",
    "https://frequentmiler.com/best-credit-card-offers/",
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
    def __init__(self, search_queries: List[str], browser):
        self.search_queries = search_queries
        self.browser = browser

    def _is_valid_link(self, url: str) -> bool:
        if not url or not url.startswith("http"): return False
        try:
            domain = url.split("://")[1].split("/")[0]
            if any(excluded in domain for excluded in EXCLUDED_DOMAINS): return False
        except IndexError: return False
        return True

    async def discover_urls(self) -> Set[str]:
        all_links = set()
        print(f"🌱 Starting URL discovery for {len(self.search_queries)} queries...")
        try:
            with DDGS() as ddgs:
                for query in self.search_queries:
                    print(f"  -> Searching for: '{query}'")
                    results = list(ddgs.text(query, max_results=3)) # Fewer results to be less aggressive
                    if not results:
                        print("     - No results found.")
                        continue
                    
                    for result in results:
                        url = result.get('href')
                        if self._is_valid_link(url):
                            all_links.add(url)
                    
                    delay = random.uniform(4, 8)
                    print(f"     - Pausing for {delay:.1f} seconds to avoid rate limit...")
                    await asyncio.sleep(delay)

        except Exception as e:
            print(f"❗️❗️ An error during DuckDuckGo search: {e}")

        if not all_links:
            print("\n⚠️ Live search failed. Switching to failsafe URLs.\n")
            return set(FAILSAFE_URLS)
        
        print(f"🌱 Discovered {len(all_links)} unique URLs.\n")
        return all_links

    async def process_links(self, urls: Set[str]) -> List[MockOpportunity]:
        tasks = [self._fetch_and_analyze(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return [result for result in results if result]

    async def _fetch_and_analyze(self, url: str) -> Optional[MockOpportunity]:
        """Uses Playwright to fetch content like a real browser."""
        page = None
        try:
            print(f"📰 Fetching with Playwright: {url}")
            page = await self.browser.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=30000) # 30s timeout
            
            # Wait for a common sign that the page has settled
            await page.wait_for_timeout(2000) 

            html_content = await page.content()
            
            text_content = extract(html_content, include_comments=False, include_tables=False)
            
            if not text_content:
                print(f"  - ❗️ Could not extract main content from {url}.")
                return None
            
            return analyze_opportunity_with_ai(text_content, source_url=url)
        except Exception as e:
            print(f"  - ❗️❗️ Unexpected error processing {url}: {e}")
            return None
        finally:
            if page:
                await page.close()

# --- Main Execution Logic ---
async def main():
    print("--- SCRIPT STARTED: PLAYWRIGHT MODE ---")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        scraper = ScraperCore(SEARCH_QUERIES, browser)
        
        urls_to_scan = await scraper.discover_urls()
        if not urls_to_scan:
            print("🛑 CRITICAL ERROR: No URLs to scan. Cannot proceed.")
            await browser.close()
            return

        print(f"🕵️ Processing {len(urls_to_scan)} URLs through the AI filter...")
        all_opportunities = await scraper.process_links(urls_to_scan)
        
        await browser.close()
        
    final_opportunities = [opp for opp in all_opportunities if opp.trust_score >= 5]
    print(f"\n✅ Found {len(final_opportunities)} valid opportunities with trust score >= 5:\n")

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

