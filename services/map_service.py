# services/map_service.py

import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from typing import List, Tuple, Dict
from core.schemas import POIModel
from core.config import Config

INTEREST_TO_TAGS: Dict[str, List[Tuple[str, str]]] = {
    "history": [
        ("historic", "castle|monument|ruins|archaeological_site|tomb|battlefield|palace|church|mosque"),
        ("tourism", "attraction|building"),
        ("amenity", "place_of_worship")
    ],
    "museums": [
        ("tourism", "museum|gallery"),
        ("amenity", "arts_centre|theatre")
    ],
    "scenic": [
        ("tourism", "viewpoint"),
        ("natural", "beach|cave_entrance|peak")
    ],
    "food": [
        ("amenity", "restaurant|food_court")
    ],
    "coffee": [
        ("amenity", "cafe"),
        ("shop", "bakery|confectionery")
    ],
    "outdoors": [
        ("leisure", "park|garden|nature_reserve")
    ],
    "nightlife": [
        ("amenity", "bar|pub|nightclub|biergarten")
    ],
    "shopping": [
        ("shop", "mall|department_store"),
        ("amenity", "market_place")
    ],
    "entertainment": [
        ("tourism", "theme_park|zoo|aquarium"),
        ("leisure", "amusement_arcade|water_park")
    ]
}

DEFAULT_TAGS: List[Tuple[str, str]] = [
    ("tourism", "museum|viewpoint|attraction"),
    ("historic", "castle|monument|ruins|palace"),
    ("amenity", "place_of_worship|restaurant|cafe"),
    ("leisure", "park|garden")
]

class MapService:
    """Using OpenStreetMap's Nominatim and Overpass APIs, this service provides geocoding and live POI fetching functionalities."""

    def __init__(self):
        self.nominatim_url = Config.NOMINATIM_URL
        self.overpass_url = Config.OVERPASS_URL

        self.headers = {"User-Agent": f"TripPlannerAIAgent/1.0 (contact: {Config.DEV_EMAIL})"}

        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get_coordinates(self, city_name: str) -> Tuple[float, float]:
        """Latitude and longitude of the given city name are fetched using the Nominatim API."""
        time.sleep(1)  # Add a delay to respect Nominatim's usage policy
        params = {
            "q": city_name,
            "format": "json",
            "limit": 1
        }
        try:
            response = self.session.get(self.nominatim_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                raise ValueError(f"City not found: {city_name}")
                
            return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as e:
            raise RuntimeError(f"Geocoding service error: {str(e)}")

    def fetch_live_pois(self, lat: float, lon: float, interests: List[str], dietary: str, boost_scores: Dict[str, float] | None = None, radius_meters: int = 10000) -> List[POIModel]:
        """Fetch live points of interest (POIs) around the specified coordinates, 
        categorizing and balancing them across user interests to prevent bias."""

        if boost_scores is None:
            boost_scores = {}
        
        target_tags = []
        for interest in interests:
            if interest in INTEREST_TO_TAGS:
                target_tags.extend(INTEREST_TO_TAGS[interest])
        
        if not target_tags:
            target_tags = DEFAULT_TAGS

        node_queries = ""
        for key, val in target_tags:
            node_queries += f'node["{key}"~"{val}"](around:{radius_meters},{lat},{lon});'
            node_queries += f'way["{key}"~"{val}"](around:{radius_meters},{lat},{lon});'
            
        overpass_query = f"""
        [out:json][timeout:60];
        (
            {node_queries}
        );
        out center;
        """

        try:
            response = self.session.post(self.overpass_url, data={"data": overpass_query}, headers=self.headers, timeout=70)
            response.raise_for_status()
            data = response.json()
            
            elements = data.get("elements", [])
            
            categorized_pois = {interest: [] for interest in interests}
            
            for elem in elements:
                poi_lat = elem.get("lat") or elem.get("center", {}).get("lat")
                poi_lon = elem.get("lon") or elem.get("center", {}).get("lon")
                
                tags_dict = elem.get("tags", {})
                name = tags_dict.get("name")

                if not name or not poi_lat or not poi_lon:
                    continue
                
                if dietary != "omnivore":
                    diet_tag = tags_dict.get(f"diet:{dietary}")
                    if diet_tag == "no":
                        continue
                    
                category = "historical" if "historical" in tags_dict else tags_dict.get("tourism") or tags_dict.get("amenity") or "point_of_interest"
                osm_id = f"{elem.get('type')}_{elem.get('id')}"

                poi_obj = POIModel(
                    poi_id=osm_id,
                    name=name,
                    category=category,
                    lat=float(poi_lat),
                    lon=float(poi_lon),
                    url=tags_dict.get("website", "")
                )

                matched = False
                for interest in interests:
                    if interest in INTEREST_TO_TAGS:
                        for tag_key, tag_val in INTEREST_TO_TAGS[interest]:
                            if tag_key in tags_dict and any(v in tags_dict[tag_key] for v in tag_val.split("|")):
                                categorized_pois[interest].append(poi_obj)
                                matched = True
                                break
                
                if not matched and interests and interests[0] in categorized_pois:
                    categorized_pois[interests[0]].append(poi_obj)

            balanced_pois = []
            max_per_interest = 8
            
            for interest, poi_list in categorized_pois.items():
                poi_list.sort(key=lambda poi: boost_scores.get(poi.poi_id, 0),reverse=True)
                seen_ids = set()
                unique_list = []
                for p in poi_list:
                    if p.poi_id not in seen_ids:
                        seen_ids.add(p.poi_id)
                        unique_list.append(p)
                
                balanced_pois.extend(unique_list[:max_per_interest])

            if not balanced_pois:
                for elem in elements[:40]:
                    poi_lat = elem.get("lat") or elem.get("center", {}).get("lat")
                    poi_lon = elem.get("lon") or elem.get("center", {}).get("lon")
                    tags_dict = elem.get("tags", {})
                    name = tags_dict.get("name")
                    if name and poi_lat and poi_lon:
                        balanced_pois.append(POIModel(
                            poi_id=f"{elem.get('type')}_{elem.get('id')}",
                            name=name,
                            category="point_of_interest",
                            lat=float(poi_lat),
                            lon=float(poi_lon),
                            url=tags_dict.get("website", "")
                        ))

            return balanced_pois[:45]
            
        except Exception as e:
            print(f"Overpass API Error: {str(e)}")
            return []