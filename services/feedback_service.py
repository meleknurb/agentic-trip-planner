# services/feedback_service.py

import json
import os
from collections import defaultdict


class FeedbackService:
    """
    Reads stored POI feedback events and converts them into ranking boost scores.

    Scoring Rules
    -------------
    👍 Upvote   : +0.25
    👎 Downvote : -0.35

    Feedback is scoped per city.
    """

    def __init__(self,feedback_file: str | None = None):
        if feedback_file:
            self.feedback_file = feedback_file
        else:
            self.feedback_file = os.path.join("feedback", "poi_feedback.jsonl")

    def calculate_boost_scores(self, city_key: str) -> dict:
        """
        Returns a dictionary like:

        {
            "node_123": 0.50,
            "way_456": -0.35,
            ...
        }
        """

        city_key = city_key.lower().strip()

        scores = defaultdict(float)

        if not os.path.exists(self.feedback_file):
            return {}

        with open(self.feedback_file, "r", encoding="utf-8") as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("city_key") != city_key:
                    continue

                poi_id = event.get("poi_id")
                vote = event.get("vote")

                if not poi_id:
                    continue

                if vote == "up":
                    scores[poi_id] += 0.25

                elif vote == "down":
                    scores[poi_id] -= 0.35

        # Prevent extremely popular or unpopular POIs from
        # permanently dominating the ranking.
        MAX_BOOST = 3.0
        MIN_BOOST = -3.0

        for poi_id in scores:
            scores[poi_id] = max(MIN_BOOST,min(MAX_BOOST, scores[poi_id]))

        return dict(scores)

    def get_boost(self, city_key: str, poi_id: str) -> float:
        """
        Returns the boost score of a single POI.

        Example:
            0.75
            -0.35
            0.0
        """

        scores = self.calculate_boost_scores(city_key)

        return scores.get(poi_id, 0.0)

    def get_feedback_statistics(self, city_key: str) -> dict:
        """
        Returns accumulated up and down vote counts for all POIs in a given city.
        Format:
        {
            "node_123": {"up": 8, "down": 2},
            "node_456": {"up": 1, "down": 6}
        }
        """
        city_key = city_key.lower().strip()
        stats = {}

        if not os.path.exists(self.feedback_file):
            return stats

        with open(self.feedback_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("city_key") != city_key:
                    continue

                poi_id = event.get("poi_id")
                vote = event.get("vote")

                if not poi_id:
                    continue

                if poi_id not in stats:
                    stats[poi_id] = {"up": 0, "down": 0}

                if vote == "up":
                    stats[poi_id]["up"] += 1
                elif vote == "down":
                    stats[poi_id]["down"] += 1

        return stats