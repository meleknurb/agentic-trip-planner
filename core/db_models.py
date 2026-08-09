# core/db_models.py

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
login_manager = LoginManager()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    travel_pace = db.Column(db.String(20), default='balanced')
    dietary_preference = db.Column(db.String(50), default='omnivore')

    itineraries = db.relationship('Itinerary', backref='owner', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Itinerary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    total_days = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    interests = db.Column(db.JSON, nullable=True, default=list)
    rag_context = db.Column(db.Text, nullable=True, default="")

    days = db.relationship('ItineraryDay', backref='itinerary', lazy=True, cascade="all, delete-orphan")

class ItineraryDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey('itinerary.id'), nullable=False)
    day_number = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    activities = db.relationship('ItineraryActivity', backref='day', lazy=True, cascade="all, delete-orphan")

class ItineraryActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey('itinerary_day.id'), nullable=False)
    slot = db.Column(db.String(50), nullable=False) # morning, afternoon, evening
    poi_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    why = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    feedback_type = db.Column(db.String(20), nullable=False)  # e.g., 'bug', 'feature', 'general'
    created_at = db.Column(db.DateTime, default=db.func.now())

class GenerationTrace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer,db.ForeignKey('itinerary.id'),nullable=False)
    generation_type = db.Column(db.String(30),nullable=False,default="initial")

    geocoding_duration = db.Column(db.Float, nullable=True)
    poi_collection_duration = db.Column(db.Float, nullable=True)
    rag_retrieval_duration = db.Column(db.Float, nullable=True)
    gemini_generation_duration = db.Column(db.Float, nullable=True)
    total_duration = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime,default=db.func.now())

    itinerary = db.relationship('Itinerary', backref=db.backref('generation_trace', lazy=True, cascade='all, delete-orphan'))