# Directory: app/term_generator/dynamic_query_builder.py
# This module expands our search query list dynamically by scraping Google.

import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import List, Set

# Headers to mimic a real browser visit for scraping Google
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class DynamicQueryBuilder:
    """
    Expands a list of seed queries by scraping "Related searches" from Google.
    This makes our scraper smarter by discovering new search vectors automatically.
    """
    def __init__(self, initial_queries: List[str]):
        self.initial_queries = initial_queries
        self.expanded_queries: Set[str] = set(initial_queries)

    async def expand_queries(self) -> List[str]:
        """
        For each initial query, fetches related search terms from Google.
        
        Returns:
            A deduplicated list of all initial and discovered queries.
        """
        print("🧠 Starting query expansion process...")
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=10.0) as client:
            tasks = [self._fetch_related_for_query(client, query) for query in self.initial_queries]
            await asyncio.gather(*tasks)

        print(f"🧠 Query expansion complete. Total queries now: {len(self.expanded_queries)}")
        return list(self.expanded_queries)

    async def _fetch_related_for_query(self, client: httpx.AsyncClient, query: str):
        """
        Scrapes a Google search results page for a single query to find related terms.
        """
        try:
            # URL-encode the query
            encoded_query = httpx.URL(query).path.encode('utf-8')
            search_url = f"https://www.google.com/search?q={encoded_query.decode()}"
            print(f"  -> Expanding from seed: '{query}'")
            response = await client.get(search_url)
            
            if response.status_code != 200:
                print(f"  - ❗️ Failed to fetch Google results for '{query}'. Status: {response.status_code}")
                return

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # This selector is more robust for finding "Related searches"
            related_search_links = soup.select("div[data-st-mc] a, a[id^='rl_']")

            found_new_term = False
            for link in related_search_links:
                related_term = link.get_text(strip=True)
                if related_term and related_term.lower() not in self.expanded_queries:
                    # More robust check for junk terms
                    if "see more" in related_term.lower() or "search" in related_term.lower() or len(related_term) > 100:
                        continue
                    self.expanded_queries.add(related_term)
                    found_new_term = True

            if not found_new_term:
                print(f"  - No new related terms found for '{query}'.")

        except Exception as e:
            print(f"  - ❗️❗️ An error occurred while expanding query '{query}': {e}")

