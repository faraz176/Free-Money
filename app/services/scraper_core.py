# Directory: app/services/financial_scraper.py
# To run this, you will need to install the following packages:
# pip install httpx beautifulsoup4 duckduckgo-search trafilatura asyncio

import asyncio
import httpx
from duckduckgo_search import DDGS
from trafilatura import fetch_url, extract
from typing import List, Set, Optional

# --- Configuration ---

# Headers to mimic a real browser visit
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Optimized search queries to find financial opportunities
SEARCH_QUERIES = [
    "credit card signup bonus offers",
    "high yield savings account bonus 2024",
    "brokerage account opening bonus",
    "unclaimed government funds lookup",
    "small business grants 2024 application",
    "student scholarships and grants financial aid",
    "manufacturer rebates and coupons",
    "class action settlement claims",
]

# Domains to exclude from search results to filter out noise
EXCLUDED_DOMAINS = [
    "google.com", "youtube.com", "facebook.com", "twitter.com",
    "linkedin.com", "instagram.com", "pinterest.com", "duckduckgo.com"
]

# --- FAILSAFE URLS ---
# This list is used if the live search returns no results.
FAILSAFE_URLS = [
    "https://www.nerdwallet.com/best/credit-cards/sign-up-bonus",
    "https://www.forbes.com/advisor/banking/best-bank-bonuses-and-promotions/",
    "https://www.unclaimed.org/", # National Association of Unclaimed Property Administrators
    "https://grants.gov"
]

# --- Mock AI Analysis Function (DEBUG VERSION) ---
class MockOpportunity:
    """A mock representation of the Opportunity object for testing."""
    def __init__(self, title: str, trust_score: int, source_url: str, summary: str = ""):
        self.title = title
        self.trust_score = trust_score
        self.source_url = source_url
        self.summary = summary

    def __repr__(self):
        return f"Opportunity(title='{self.title}', score={self.trust_score})"

def analyze_opportunity_with_ai(text_content: str, source_url: str) -> Optional[MockOpportunity]:
    """
    DEBUG Mock function that simulates an AI analyzing content.
    It's now less strict and provides feedback on why it might reject content.
    """
    print(f"🤖 AI: Analyzing content from: {source_url}")
    text_lower = text_content.lower()
    
    high_confidence_keywords = ["bonus", "grant", "rebate", "scholarship", "claim", "settlement", "unclaimed"]

    if any(keyword in text_lower for keyword in high_confidence_keywords):
        print("  - ✅ AI: High-confidence keyword found. Passing as opportunity.")
        return MockOpportunity(
            title="Potential Financial Opportunity Found",
            trust_score=7,
            source_url=source_url,
            summary="This page appears to contain information about a financial bonus, grant, or similar opportunity."
        )
    
    elif len(text_content) > 500:
         print("  - ⚠️ AI: No high-confidence keywords, but content is substantial. Passing as low-confidence opportunity.")
         return MockOpportunity(
            title="Low-Confidence Opportunity",
            trust_score=3,
            source_url=source_url,
            summary="Page has substantial content but no specific financial keywords were detected."
        )
    
    print(f"  - ❌ AI: Content from {source_url} is too short or irrelevant. Rejecting.")
    return None


# --- Core Scraper Class ---
class FinancialScraper:
    """
    A scraper to discover and validate financial opportunities from the web.
    """
    def _is_valid_link(self, url: str) -> bool:
        """Filters out invalid or excluded links."""
        if not url or not url.startswith("http"):
            return False
        try:
            domain = url.split("://")[1].split("/")[0]
            if any(excluded in domain for excluded in EXCLUDED_DOMAINS):
                return False
        except IndexError:
            return False
        return True

    async def discover_seed_urls(self) -> Set[str]:
        """
        Uses DuckDuckGo to find initial "seed" URLs.
        If the search fails, it returns the failsafe list.
        """
        all_links = set()
        print("🌱 Starting seed URL discovery via live web search...")
        try:
            with DDGS() as ddgs:
                for query in SEARCH_QUERIES:
                    print(f"  -> Searching for: '{query}'")
                    results = list(ddgs.text(query, max_results=10))
                    if not results:
                        print(f"  - No results returned for query: '{query}'")
                        continue
                    
                    for result in results:
                        url = result.get('href')
                        if self._is_valid_link(url):
                            all_links.add(url)
        except Exception as e:
            print(f"❗️❗️ An error occurred during DuckDuckGo search: {e}")

        if not all_links:
            print("\n⚠️ Live search failed to find any valid URLs.")
            print("✅ Switching to failsafe mode and using pre-vetted URLs.\n")
            return set(FAILSAFE_URLS)
        
        print(f"🌱 Discovered {len(all_links)} unique and valid seed URLs from live search.\n")
        return all_links

    async def process_links_with_ai(self, urls: Set[str]) -> List[MockOpportunity]:
        """Processes a list of URLs concurrently and returns the results."""
        async with httpx.AsyncClient(headers=HEADERS, timeout=20.0, follow_redirects=True) as client:
            tasks = [self._fetch_and_analyze(client, url) for url in urls]
            results = await asyncio.gather(*tasks)
        
        # Filter out None results from failed tasks
        opportunities = [result for result in results if result]
        return opportunities

    async def _fetch_and_analyze(self, client: httpx.AsyncClient, url: str) -> Optional[MockOpportunity]:
        """Fetches a single URL, extracts its content, and analyzes it."""
        try:
            print(f"📰 Fetching and extracting content from: {url}")
            # Use trafilatura's fetch_url which is a blocking call.
            # We run it in a separate thread to not block the asyncio event loop.
            loop = asyncio.get_running_loop()
            downloaded = await loop.run_in_executor(None, fetch_url, url)

            if not downloaded:
                print(f"  - ❗️ Fetch failed for {url}. The site may be down or blocking requests.")
                return None
            
            # The extraction part is CPU-bound, so it's okay to run directly.
            text_content = extract(downloaded, include_comments=False, include_tables=False)
            if not text_content:
                print(f"  - ❗️ Trafilatura could not extract main content from {url}.")
                return None
            
            print(f"  - Extracted ~{len(text_content)} characters of text.")
            return analyze_opportunity_with_ai(text_content, source_url=url)
        except Exception as e:
            print(f"  - ❗️❗️ An unexpected error occurred while processing {url}: {e}")
            return None

# --- Main Execution Logic ---
async def main():
    """Main function to run the complete scraping and analysis pipeline."""
    print("--- SCRIPT STARTED ---")
    scraper = FinancialScraper()
    
    seed_urls = await scraper.discover_seed_urls()
    
    if not seed_urls:
        print("🛑 CRITICAL ERROR: No seed URLs found from search or failsafe. Cannot proceed.")
        return

    print(f"🕵️ Processing {len(seed_urls)} URLs through the AI filter...")
    all_processed_opps = await scraper.process_links_with_ai(seed_urls)
    
    print(f"\n📊 AI processing complete. Found {len(all_processed_opps)} total items (including low-confidence).")
    
    final_opportunities = [opp for opp in all_processed_opps if opp.trust_score >= 5]
    
    print(f"✅ Found {len(final_opportunities)} valid opportunities with trust score >= 5:\n")

    if not final_opportunities:
        print("  - While pages were analyzed, none met the final trust score threshold of 5.")
        print("  - Check the logs above to see why pages were rejected or had low scores.")
    else:
        final_opportunities.sort(key=lambda x: x.trust_score, reverse=True)
        output_lines = [f"- {opp.title} ({opp.trust_score}/10)\n  Source: {opp.source_url}\n" for opp in final_opportunities]
        
        for line in output_lines:
            print(line)

        with open("financial_opportunities.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        print("\n📄 Results saved to financial_opportunities.txt")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"💥 An unexpected error occurred at the top level: {e}")
    finally:
        print("--- SCRIPT FINISHED ---")
