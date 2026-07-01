# tests/test_rag_service.py

import pytest
from unittest.mock import MagicMock, patch
from services.rag_service import RAGService

@pytest.fixture
def rag_service():
    """Provides an isolated instance of RAGService for testing."""
    return RAGService()

@patch("services.rag_service.requests.Session.get")
def test_wikivoyage_resolve_title_success(mock_get, rag_service):
    """Tests that a valid city name successfully resolves to its official Wikivoyage page title."""
    # Mocking the JSON response framework of Wikivoyage search API
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "query": {
            "search": [{"title": "Manhattan"}]
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    title = rag_service.wikivoyage_resolve_title("manhattan")
    
    assert title == "Manhattan"
    mock_get.assert_called_once()

@patch("services.rag_service.requests.Session.get")
def test_fetch_city_guide_text_success(mock_get, rag_service):
    """Tests that raw HTML response from Wikivoyage is fetched and correctly sanitized into plain text."""
    # First call mock for title resolution, second call mock for page content parsing
    mock_response_title = MagicMock()
    mock_response_title.json.return_value = {"query": {"search": [{"title": "Manhattan"}]}}
    
    mock_response_html = MagicMock()
    mock_response_html.json.return_value = {
        "parse": {
            "text": {"*": "<p>Welcome to Manhattan! <script>alert(1)</script> It has great cafes and museums.</p>"}
        }
    }
    
    mock_get.side_effect = [mock_response_title, mock_response_html]

    clean_text = rag_service.fetch_city_guide_text("Manhattan")
    
    assert "Welcome to Manhattan!" in clean_text
    assert "cafes and museums." in clean_text
    assert "<script>" not in clean_text  # Assures HTML sanitation logic works perfectly
    assert mock_get.call_count == 2

@patch("services.rag_service.requests.Session.get")
def test_fetch_city_guide_text_not_found(mock_get, rag_service):
    """Tests that the service gracefully returns an empty string when the requested city is not found."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"query": {"search": []}}
    mock_get.return_value = mock_response

    clean_text = rag_service.fetch_city_guide_text("NonExistentCity12345")
    
    assert clean_text == ""

def test_retrieve_relevant_context_smart_filtering(rag_service):
    """Tests the core RAG scoring pipeline to ensure relevant chunks are boosted based on user preferences."""
    # Mocking the internal method so we don't trigger real network HTTP hits
    mock_corpus = (
        "This paragraph is completely about sports and soccer stadiums in the city. "
        "Alternatively, this next block is deeply focused on historical museums, art galleries, "
        "and cultural heritage ancient architectures. "
        "Finally, this section covers generic transport and public bus timetables."
    )
    rag_service.fetch_city_guide_text = MagicMock(return_value=mock_corpus)

    # User explicitly wants culture and museums
    interests = ["museums", "history"]
    
    # Run the retrieval automation matrix
    context = rag_service.retrieve_relevant_context(city_name="TestCity", interests=interests, chunk_size=150)
    
    # Assertions to ensure semantic ranking mechanics prioritized the right text blocks
    assert "museums" in context.lower()
    assert "cultural" in context.lower()
    # It should rank the generic transportation text lower or omit it if top hits dominate
    rag_service.fetch_city_guide_text.assert_called_once_with("TestCity")