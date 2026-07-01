# agent/gemini_agent.py

import json
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError 

from core.config import Config
from core.schemas import TripItineraryModel, POIModel
from agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


class GeminiAgent:
    """The core AI engine that processes live data and context to generate a structured travel itinerary using Gemini 2.5 Flash."""

    def __init__(self):
        api_key = Config.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY could not be found in Config. Please verify your environment variables.")

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def generate_itinerary(self, city_name: str, total_days: int, live_pois: list[POIModel], rag_context: str, interests: list[str]) -> TripItineraryModel:
        """Converts map points and RAG contexts into a strict Pydantic-validated TripItineraryModel."""
        
        if not live_pois:
            raise ValueError("Cannot generate an itinerary without live map points.")

        map_points_data = [poi.model_dump() for poi in live_pois]
        map_points_json = json.dumps(map_points_data, ensure_ascii=False, indent=2)

        interests_str = ", ".join(interests) if interests else "General Sightseeing"

        user_content = USER_PROMPT_TEMPLATE.format(
            total_days=total_days,
            city_name=city_name,
            interests=interests_str,
            map_points_json=map_points_json,
            rag_context=rag_context.strip() if rag_context and rag_context.strip() else "No specific destination guide text available for this request. Please rely on your extensive internal knowledge base to fulfill the requirements."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                    response_mime_type="application/json",
                    response_schema=TripItineraryModel, 
                ),
            )

            return TripItineraryModel.model_validate_json(response.text)

        except APIError as ae:
            raise RuntimeError(f"Gemini API Error occurred: {ae.message} (Status Code: {ae.code})")
        except ValidationError as ve:
            raise RuntimeError(f"Gemini output structural validation failed against TripItineraryModel: {str(ve)}")
        except Exception as e:
            raise RuntimeError(f"Gemini Agent execution failed due to an unexpected error: {str(e)}")