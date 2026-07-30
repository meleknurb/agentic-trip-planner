# tests/test_feedback_service.py

import json
import pytest

from services.feedback_service import FeedbackService


@pytest.fixture
def feedback_service(tmp_path):
    """
    Creates a temporary JSONL feedback file and injects its path into FeedbackService.
    """
    feedback_path = tmp_path / "poi_feedback.jsonl"
    return FeedbackService(str(feedback_path))


def test_empty_feedback_returns_empty_scores(feedback_service):
    """An empty feedback file should return an empty score dictionary."""
    scores = feedback_service.calculate_boost_scores("paris")
    assert scores == {}


def test_upvote_boost(feedback_service):
    """Each upvote should add +0.25 to the POI score."""
    events = [
        {"city_key": "paris", "poi_id": "node_1", "vote": "up"},
        {"city_key": "paris", "poi_id": "node_1", "vote": "up"}
    ]

    with open(feedback_service.feedback_file, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    scores = feedback_service.calculate_boost_scores("paris")
    assert scores["node_1"] == pytest.approx(0.50)


def test_downvote_penalty(feedback_service):
    """Each downvote should subtract 0.35."""
    events = [
        {"city_key": "paris", "poi_id": "node_2", "vote": "down"}
    ]

    with open(feedback_service.feedback_file, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    scores = feedback_service.calculate_boost_scores("paris")
    assert scores["node_2"] == pytest.approx(-0.35)


def test_mixed_votes(feedback_service):
    """Upvotes and downvotes should accumulate correctly."""
    events = [
        {"city_key": "paris", "poi_id": "node_5", "vote": "up"},
        {"city_key": "paris", "poi_id": "node_5", "vote": "up"},
        {"city_key": "paris", "poi_id": "node_5", "vote": "down"}
    ]

    with open(feedback_service.feedback_file, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    scores = feedback_service.calculate_boost_scores("paris")
    # 0.25 + 0.25 - 0.35 = 0.15
    assert scores["node_5"] == pytest.approx(0.15)


def test_city_scope(feedback_service):
    """Feedback must only affect the matching city."""
    events = [
        {"city_key": "paris", "poi_id": "node_1", "vote": "up"},
        {"city_key": "london", "poi_id": "node_1", "vote": "down"}
    ]

    with open(feedback_service.feedback_file, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    paris_scores = feedback_service.calculate_boost_scores("paris")
    london_scores = feedback_service.calculate_boost_scores("london")

    assert paris_scores["node_1"] == pytest.approx(0.25)
    assert london_scores["node_1"] == pytest.approx(-0.35)