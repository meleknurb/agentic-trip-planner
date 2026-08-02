# agent/gemini_agent.py

import json
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError 

from core.config import Config
from core.schemas import TripItineraryModel, POIModel
from agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, REGENERATE_PROMPT_TEMPLATE, SINGLE_DAY_REGENERATE_TEMPLATE


class GeminiAgent:
    """The core AI engine that processes live data and context to generate a structured travel itinerary using Gemini 2.5 Flash."""

    def __init__(self):
        api_key = Config.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY could not be found in Config. Please verify your environment variables.")

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def generate_itinerary(self, city_name: str, total_days: int, live_pois: list[POIModel], rag_context: str, interests: list[str], user_preferences: dict) -> TripItineraryModel:
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
            rag_context=rag_context.strip() if rag_context and rag_context.strip() else "No specific destination guide text available for this request. Please rely on your extensive internal knowledge base to fulfill the requirements.",
            pace_setting=user_preferences.get('pace', 'balanced'),
            diet_setting=user_preferences.get('diet', 'omnivore')
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
            raise RuntimeError("Gemini service is temporarily unavailable. Please try again in a few moments.")
        except ValidationError as ve:
            raise RuntimeError(f"Gemini output structural validation failed against TripItineraryModel: {str(ve)}")
        except Exception as e:
            raise RuntimeError(f"Gemini Agent execution failed due to an unexpected error: {str(e)}")

    def regenerate_itinerary(self, city_name: str, total_days: int, live_pois: list[POIModel], old_itinerary_text: str, feedback: str, rag_context: str, interests: list[str], user_preferences: dict) -> TripItineraryModel:
        """Modifies and rebuilds an existing travel layout by forcing Gemini to ingest custom user feedback."""
        
        if not live_pois:
            raise ValueError("Cannot regenerate an itinerary without live map points.")

        map_points_data = [poi.model_dump() for poi in live_pois]
        map_points_json = json.dumps(map_points_data, ensure_ascii=False, indent=2)

        user_content = REGENERATE_PROMPT_TEMPLATE.format(
            city_name=city_name,
            total_days=total_days,
            old_itinerary_text=old_itinerary_text,
            feedback=feedback,
            map_points_json=map_points_json,
            rag_context=rag_context,
            interests=interests,
            pace_setting=user_preferences.get('pace', 'balanced'),
            diet_setting=user_preferences.get('diet', 'omnivore')
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.4, # Slightly higher temperature for creative adjustments
                    response_mime_type="application/json",
                    response_schema=TripItineraryModel, 
                ),
            )

            return TripItineraryModel.model_validate_json(response.text)

        except APIError as ae:
            raise RuntimeError("Gemini service is temporarily unavailable. Please try again in a few moments.")
        except ValidationError as ve:
            raise RuntimeError(f"Gemini output structural validation failed during regeneration: {str(ve)}")
        except Exception as e:
            raise RuntimeError(f"Gemini Agent regeneration pipeline failed: {str(e)}")

    def regenerate_single_day(self, city_name: str, target_day_number: int, total_days: int, live_pois: list[POIModel], old_day_text: str, feedback: str, rag_context: str, interests: list[str], user_preferences: dict, other_days_summary:str) -> TripItineraryModel:
        """Modifies and rebuilds ONLY a specific day of an existing travel itinerary based on user feedback."""
        
        if not live_pois:
            raise ValueError("Cannot regenerate a day without live map points.")

        map_points_data = [poi.model_dump() for poi in live_pois]
        map_points_json = json.dumps(map_points_data, ensure_ascii=False, indent=2)

        user_content = SINGLE_DAY_REGENERATE_TEMPLATE.format(
            city_name=city_name,
            target_day_number=target_day_number,
            total_days=total_days,
            old_day_text=old_day_text,
            feedback=feedback,
            map_points_json=map_points_json,
            rag_context=rag_context,
            interests=", ".join(interests) if interests else "General Sightseeing",
            pace_setting=user_preferences.get('pace', 'balanced'),
            diet_setting=user_preferences.get('diet', 'omnivore'),
            other_days_activities=other_days_summary
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.4,
                    response_mime_type="application/json",
                    response_schema=TripItineraryModel, 
                ),
            )
            return TripItineraryModel.model_validate_json(response.text)

        except APIError as ae:
            raise RuntimeError("Gemini service is temporarily unavailable. Please try again in a few moments.")
        except ValidationError as ve:
            raise RuntimeError(f"Gemini output structural validation failed during single day regeneration: {str(ve)}")
        except Exception as e:
            raise RuntimeError(f"Gemini Agent single day regeneration pipeline failed: {str(e)}")