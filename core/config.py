import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration class.
    Acts as the Single Source of Truth for environment variables.
    """
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    DEV_EMAIL = os.getenv("DEV_EMAIL")

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    OVERPASS_URL ="https://overpass-api.de/api/interpreter"
    WIKIVOYAGE_URL = "https://en.wikivoyage.org/w/api.php"