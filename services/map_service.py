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
            total=5,
            connect=5,
            read=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True
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

            # Handle malformed JSON responses
            try:
                data = response.json()
            except ValueError:
                raise RuntimeError("Geocoding service returned an invalid response.")

            # Validate response structure
            if not isinstance(data, list):
                raise RuntimeError("Geocoding service returned an unexpected response format.")
            
            if not data:
                raise ValueError(f"City '{city_name}' was not found.")

            first_result = data[0]
            if not isinstance(first_result, dict):
                raise RuntimeError("Geocoding service returned an unexpected response format.")

            if "lat" not in first_result or "lon" not in first_result:
                raise RuntimeError("Geocoding service response is missing latitude or longitude.")

            try:
                lat = float(first_result["lat"])
                lon = float(first_result["lon"])
            except (TypeError, ValueError):
                raise RuntimeError("Geocoding service returned invalid latitude or longitude values.")
            
            return lat, lon

        except requests.RequestException as e:
            raise RuntimeError(f"Geocoding service unavailable: {e}")

    def fetch_live_pois(self, lat: float, lon: float, interests: List[str], dietary: str, boost_scores: Dict[str, float] | None = None, radius_meters: int = 10000) -> List[POIModel]:
        """
        Fetch live points of interest (POIs) around the specified coordinates, categorizing and balancing them across user interests to prevent bias.
        """

        if boost_scores is None:
            boost_scores = {}

        target_tags: List[Tuple[str, str]] = []

        for interest in interests:
            if interest in INTEREST_TO_TAGS:
                target_tags.extend(INTEREST_TO_TAGS[interest])

        if not target_tags:
            target_tags = DEFAULT_TAGS

        grouped_tags: Dict[str, set[str]] = {}

        for key, values in target_tags:
            grouped_tags.setdefault(key, set()).update(values.split("|"))


        query_fragments: List[str] = []

        for key in sorted(grouped_tags):
            values = grouped_tags[key]
            regex = "|".join(sorted(values))

            query_fragments.append(
                f'node["{key}"~"{regex}"]["name"]'
                f'(around:{{radius}},{lat},{lon});'
            )

            query_fragments.append(
                f'way["{key}"~"{regex}"]["name"]'
                f'(around:{{radius}},{lat},{lon});'
            )

        query_template = f"""
        [out:json][timeout:60];
        (
            {"".join(query_fragments)}
        );
        out tags center qt;
        """

        candidate_radii = [radius for radius in (5000, radius_meters) if radius <= radius_meters]
        search_radii = list(dict.fromkeys(candidate_radii))

        if not search_radii:
            search_radii = [radius_meters]

        target_poi_count = min(45,max(8, len(interests) * 8))

        last_error = None
        best_pois: List[POIModel] = []

        for current_radius in search_radii:
            overpass_query = query_template.format(radius=current_radius)

            try:
                response = self.session.post(
                    self.overpass_url,
                    data={"data": overpass_query},
                    headers=self.headers,
                    timeout=70
                )

                response.raise_for_status()

                try:
                    data = response.json()
                except ValueError:
                    raise RuntimeError("Overpass API returned an invalid response.")

                if not isinstance(data, dict):
                    raise RuntimeError("Overpass API returned an unexpected response format.")

                elements = data.get("elements", [])

                if not isinstance(elements, list):
                    raise RuntimeError("Overpass API returned invalid POI data.")

                categorized_pois = {interest: [] for interest in interests}

                for elem in elements:
                    if not isinstance(elem, dict):
                        continue

                    center = elem.get("center", {})

                    if not isinstance(center, dict):
                        center = {}

                    poi_lat = (elem.get("lat") if elem.get("lat") is not None else center.get("lat"))
                    poi_lon = (elem.get("lon") if elem.get("lon") is not None else center.get("lon"))

                    tags_dict = elem.get("tags", {})

                    if not isinstance(tags_dict, dict):
                        continue

                    name = tags_dict.get("name")

                    if not name or poi_lat is None or poi_lon is None:
                        continue

                    if dietary != "omnivore":
                        diet_tag = tags_dict.get(f"diet:{dietary}")

                        if diet_tag == "no":
                            continue

                    category = (tags_dict.get("historic") or tags_dict.get("tourism") or tags_dict.get("amenity") or "point_of_interest")

                    osm_id = (f"{elem.get('type')}_{elem.get('id')}")

                    try:
                        poi_obj = POIModel(
                            poi_id=osm_id,
                            name=name,
                            category=category,
                            lat=float(poi_lat),
                            lon=float(poi_lon),
                            url=tags_dict.get("website", "")
                        )
                    except (TypeError, ValueError):
                        continue

                    matched = False
                    for interest in interests:

                        if interest not in INTEREST_TO_TAGS:
                            continue

                        for tag_key, tag_val in INTEREST_TO_TAGS[interest]:
                            tag_value = tags_dict.get(tag_key)

                            if not isinstance(tag_value, str):
                                continue

                            possible_values = tag_val.split("|")

                            if any(value in tag_value for value in possible_values):
                                categorized_pois[interest].append(poi_obj)
                                matched = True
                                break

                        if matched:
                            break

                    if (not matched and interests and interests[0] in categorized_pois):
                        categorized_pois[interests[0]].append(poi_obj)


                balanced_pois: List[POIModel] = []
                max_per_interest = 8

                for interest, poi_list in categorized_pois.items():
                    poi_list.sort(key=lambda poi: boost_scores.get(poi.poi_id,0),reverse=True)
                    seen_ids = set()
                    unique_list = []

                    for poi in poi_list:
                        if poi.poi_id in seen_ids:
                            continue
                        seen_ids.add(poi.poi_id)
                        unique_list.append(poi)

                    balanced_pois.extend(unique_list[:max_per_interest])

                balanced_pois = balanced_pois[:45]

                if len(balanced_pois) > len(best_pois):
                    best_pois = balanced_pois

                if len(balanced_pois) >= target_poi_count:
                    return balanced_pois

            except requests.RequestException as e:
                last_error = e
                continue

            except RuntimeError as e:
                last_error = e
                continue

        if best_pois:
            return best_pois[:45]

        if last_error is not None:
            if isinstance(last_error,requests.RequestException):
                raise RuntimeError(f"Overpass API is unavailable: {last_error}")
            raise RuntimeError(str(last_error))

        return []