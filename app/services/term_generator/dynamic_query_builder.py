# Directory: app/term_generator/dynamic_query_builder.py
# This module expands our search query list dynamically by scraping Google.

import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import List, Set
import urllib.parse

# Headers to mimic a real browser visit for scraping Google
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1'
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
            # URL-encode the query properly
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}&gl=us&hl=en"
            print(f"  -> Expanding from seed: '{query}'")
            response = await client.get(search_url)
            
            if response.status_code != 200:
                print(f"  - ❗️ Failed to fetch Google results for '{query}'. Status: {response.status_code}")
                # Optional: Write response.text to a file for debugging what Google sent back
                # with open(f"error_{query[:10]}.html", "w", encoding="utf-8") as f:
                #     f.write(response.text)
                return

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # --- NEW ROBUST METHOD ---
            # Instead of a single selector, we check multiple known containers.
            found_new_terms = set()
            
            # Selector for the main "Related searches" block at the bottom
            related_searches_div = soup.find('div', id='bres')
            if related_searches_div:
                links = related_searches_div.find_all('a')
                for link in links:
                    found_new_terms.add(link.get_text(strip=True))

            # Selector for "People also ask" sections
            people_also_ask_divs = soup.find_all('div', jsname='Cpkphb')
            for div in people_also_ask_divs:
                question = div.find('span')
                if question:
                    found_new_terms.add(question.get_text(strip=True))
            
            # Clean and filter the collected terms
            final_new_terms = []
            for term in found_new_terms:
                if term and len(term) > 3 and term.lower() not in self.expanded_queries:
                    if "›" in term or "See more" in term:
                        continue
                    final_new_terms.append(term)


            if final_new_terms:
                print(f"  - Found new terms: {final_new_terms}")
                self.expanded_queries.update(final_new_terms)
            else:
                print(f"  - No new related terms found for '{query}'. Google's layout may have changed.")

        except Exception as e:
            print(f"  - ❗️❗️ An error occurred while expanding query '{query}': {e}")
