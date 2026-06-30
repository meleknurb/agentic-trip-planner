# tests/test_map_service.py

import pytest
from unittest.mock import MagicMock, patch
from services.map_service import MapService
from core.schemas import POIModel

@pytest.fixture
def map_service():
    """Pytest fixture to provide a MapService instance for tests."""
    return MapService()


# 1. GEOCODING TEST
@patch('requests.Session.get')
def test_get_coordinates_success(mock_get, map_service):
    """Test get_coordinates by mocking the Nominatim API response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"lat": "41.0082", "lon": "28.9784"}]
    mock_get.return_value = mock_response

    lat, lon = map_service.get_coordinates("Istanbul")
    
    assert lat == 41.0082
    assert lon == 28.9784


# 2. LIVE POI FETCHING & SCHEMA TEST
@patch('requests.Session.post')
def test_fetch_live_pois_strict_schema_validation(mock_post, map_service):
    """Validate that Overpass API responses are accurately parsed into POIModel schemas."""
    mock_overpass_data = {
        "elements": [
            {
                "type": "node",
                "id": 123456,
                "lat": 41.0,
                "lon": 29.0,
                "tags": {
                    "name": "Sample Coffee Shop",
                    "amenity": "cafe"
                }
            }
        ]
    }
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_overpass_data
    mock_post.return_value = mock_response

    pois = map_service.fetch_live_pois(lat=41.0, lon=29.0, interests=["coffee"])

    assert isinstance(pois, list)
    assert len(pois) == 1
    assert isinstance(pois[0], POIModel)
    assert pois[0].name == "Sample Coffee Shop"


# 3. RETRY MECHANISM TEST 
@patch('requests.Session.post')
def test_map_service_retry_on_server_failure(mock_post, map_service):
    """Verify that fetch_live_pois safely returns an empty list on failure after its internal session logic."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("504 Gateway Timeout")
    mock_post.return_value = mock_response
    
    pois = map_service.fetch_live_pois(lat=41.0, lon=29.0, interests=["coffee"])
    
    assert pois == []