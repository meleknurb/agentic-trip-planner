# services/rag_service.py

import requests
import re
from typing import Optional, List
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from core.config import Config

class RAGService:
    def __init__(self):
        self.wikivoyage_url = Config.WIKIVOYAGE_URL
        self.headers = {"User-Agent": f"TripPlannerAIAgent/1.0 (contact: {Config.DEV_EMAIL})"}
        
        # Built-in resilient HTTP Session configuration
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def wikivoyage_resolve_title(self, city: str) -> Optional[str]:
        """Resolves the user-inputted city name to the closest official Wikivoyage page title."""
        params = {
            "action": "query",
            "list": "search",
            "srsearch": city,
            "srlimit": 1,
            "format": "json"
        }
        try:
            response = self.session.get(self.wikivoyage_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            search_results = response.json().get("query", {}).get("search", [])
            return search_results[0]["title"] if search_results else None
        except Exception as e:
            print(f"Wikivoyage Title Resolve Error: {str(e)}")
            return None

    def fetch_city_guide_text(self, city_name: str) -> str:
        """Fetches the raw city guide HTML content and sanitizes it into plain text."""
        title = self.wikivoyage_resolve_title(city_name)
        if not title:
            return ""

        params = {
            "action": "parse",
            "page": title,
            "prop": "text",
            "format": "json"
        }
        try:
            response = self.session.get(self.wikivoyage_url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            html = response.json().get("parse", {}).get("text", {}).get("*", "")

            if not html:
                return ""

            # Remove scripts, styles, and tags
            text = re.sub(r"<(script|style).*?>.*?</\1>", " ", html, flags=re.S | re.I)
            text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
            text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
            text = re.sub(r"<.*?>", " ", text, flags=re.S)
            text = re.sub(r"\s+", " ", text).strip()

            return text
        except Exception as e:
            print(f"Wikivoyage Content Fetch Error: {str(e)}")
            return ""

    def retrieve_relevant_context(self, city_name: str, interests: List[str], pace: str, dietary: str, chunk_size: int = 1200) -> str:
        """
        Advanced RAG Pipeline Component: Fetches the corpus, applies smart chunking, 
        and scores chunks based on keyword overlap with user interests to deliver optimized context.
        """
        full_text = self.fetch_city_guide_text(city_name)
        if not full_text:
            return ""

        # Split by paragraphs or clean windows to maintain semantics
        paragraphs = full_text.split(". ")
        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) < chunk_size:
                current_chunk += paragraph + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + ". "
        if current_chunk:
            chunks.append(current_chunk.strip())

        # Scoring Engine
        scored_chunks = []
        for chunk in chunks:
            score = 0
            chunk_lower = chunk.lower()
            # Boost score based on keyword frequency match with user preferences
            for interest in interests:
                # Direct match or sub-string match amplification
                matches = re.findall(rf"\b{re.escape(interest)}\b", chunk, flags=re.I)
                score += len(matches) * 2.0
            
            if pace == "relaxed":
                if any(kw in chunk_lower for kw in ["relax", "quiet", "leisurely", "park", "garden", "stroll"]):
                    score += 2.0
            elif pace == "packed":
                if any(kw in chunk_lower for kw in ["iconic", "must-see", "tourist", "busy", "main", "landmark"]):
                    score += 2.0
            elif pace == "balanced":
                score += 0.0
            
            if dietary != "omnivore":
                diet_map = {
                    "lactose-intolerant": ["dairy-free", "lactose free", "no milk"],
                    "gluten-free": ["gluten-free", "gluten free"],
                    "vegan": ["vegan", "plant-based"],
                    "vegetarian": ["vegetarian", "meat-free"],
                    "halal": ["halal", "muslim-friendly"],
                    "kosher": ["kosher", "jewish food"]
                }
                if dietary in diet_map:
                    for keyword in diet_map[dietary]:
                        if keyword in chunk_lower:
                            score += 2.0
                            break

            scored_chunks.append((score, chunk))

        # Sort chunks descending by relevancy score and pick top hits
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Take the most relevant chunks up to a reasonable length to fit nicely into the prompt window
        top_chunks = [chunk for score, chunk in scored_chunks[:4]]
        
        # Fallback to absolute baseline if no specific interest tags matched heavily
        if not top_chunks:
            return full_text[:4000]

        return "\n\n---\n\n".join(top_chunks)