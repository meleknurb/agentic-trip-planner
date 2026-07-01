# tests/test_gemini_agent.py

import pytest
from unittest.mock import MagicMock, patch

from agent.gemini_agent import GeminiAgent
from core.schemas import POIModel, TripItineraryModel

@pytest.fixture
def gemini_agent():
    """Fixture to provide a GeminiAgent instance with decoupled environment requirements."""
    # Patching the client initialization directly inside the fixture to isolate tests 
    with patch("agent.gemini_agent.genai.Client"):
        agent = GeminiAgent()
        yield agent

@pytest.fixture
def generic_mock_pois():
    """Provides general, non-hardcoded POI mock samples for agnostic destination testing."""
    return [
        POIModel(
            poi_id="node_abc123",
            name="Generic Cultural Heritage Museum",
            category="tourism=museum",
            lat=40.7128,
            lon=-74.0060,
            url="https://example-museum.org"
        ),
        POIModel(
            poi_id="node_xyz789",
            name="Authentic Local Culinary Bistro",
            category="amenity=restaurant",
            lat=40.7130,
            lon=-74.0065,
            url=""
        )
    ]

@patch("agent.gemini_agent.genai.Client")
def test_generate_itinerary_success(mock_client_class, gemini_agent, generic_mock_pois):
    """Tests that the AI engine gracefully coordinates prompt synthesis and returns structured output."""
    # Set up mock model behavior simulating a perfect structured JSON string transmission
    mock_client = MagicMock()
    gemini_agent.client = mock_client
    
    mock_response = MagicMock()
    mock_response.text = """{
        "title": "Exploration Plan",
        "city": "TestCity",
        "total_days": 1,
        "rag_context": "Tailored summary showcasing deep focus on museums and fine dining experience.",
        "days": [
            {
                "day": 1,
                "notes": "Seamless generic travel optimization tips.",
                "morning": [
                    {
                        "poi_id": "node_abc123",
                        "name": "Generic Cultural Heritage Museum",
                        "why": "Matches user's explicitly highlighted interest in local arts and global histories."
                    }
                ],
                "afternoon": [],
                "evening": []
            }
        ]
    }"""
    mock_client.models.generate_content.return_value = mock_response

    # Trigger the orchestration engine
    itinerary = gemini_agent.generate_itinerary(
        city_name="TestCity",
        total_days=1,
        live_pois=generic_mock_pois,
        rag_context="[See]\nHistoric landmarks documentation block.\n[Eat]\nTop culinary districts notes.",
        interests=["museums", "dining"]
    )

    # Dynamic assertions validating model compliance
    assert isinstance(itinerary, TripItineraryModel)
    assert itinerary.city == "TestCity"
    assert len(itinerary.days) == 1
    assert itinerary.days[0].day == 1
    
    # Verify the specific ID alignment
    assert itinerary.days[0].morning[0].poi_id == "node_abc123"
    mock_client.models.generate_content.assert_called_once()

def test_generate_itinerary_missing_live_pois(gemini_agent):
    """Assures the engine immediately fires a defensive ValueError when execution is triggered without mapping data."""
    with pytest.raises(ValueError, match="Cannot generate an itinerary without live map points."):
        gemini_agent.generate_itinerary(
            city_name="TestCity",
            total_days=2,
            live_pois=[],  # Edge case simulation
            rag_context="Valid context text",
            interests=["culture"]
        )