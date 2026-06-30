# core/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional

class POIModel(BaseModel):
    """OpenStreetMap based Point of Interest (POI) model for representing a location."""
    poi_id: str = Field(description="The unique identifier for the Point of Interest (POI) in OpenStreetMap")
    name: str = Field(description="The official or known name of the location")
    category: str = Field(description="The category of the location (e.g., amenity:restaurant, tourism:museum)")
    lat: float = Field(description="The latitude coordinate of the location")
    lon: float = Field(description="The longitude coordinate of the location")
    url: Optional[str] = Field(default="", description="The website URL of the location, if available")

class TimeBlockModel(BaseModel):
    """Time block model representing a specific activity or visit to a POI within a day."""
    poi_id: str = Field(description="The poi_id of the location to visit. Must match items in the live list.")
    why: str = Field(description="A short, attention-grabbing, and unique explanation of why the agent chose this location")

class DayPlanModel(BaseModel):
    """Day plan model representing the morning, afternoon, and evening activities for a day."""
    day: int = Field(description="The day number (e.g., 1, 2, 3)")
    morning: List[TimeBlockModel] = Field(default=[], description="List of activities to be done in the morning")
    afternoon: List[TimeBlockModel] = Field(default=[], description="List of activities to be done in the afternoon")
    evening: List[TimeBlockModel] = Field(default=[], description="List of activities to be done in the evening")
    notes: Optional[str] = Field(default="", description="General tips for the day, transportation, or weather recommendations")

class TripItineraryModel(BaseModel):
    """Final structured travel itinerary output that Gemini must return."""
    title: str = Field(description="Elegant title for the travel plan (e.g., Historical and Culinary Delights in Bursa)")
    city: str = Field(description="The name of the city being visited")
    days: List[DayPlanModel] = Field(description="Day-by-day travel plan details")
    rag_context: str = Field(description="Your tailored English Markdown summary based on the guide data and user preferences.")