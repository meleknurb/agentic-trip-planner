# app.py

import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.csrf import CSRFProtect
from flask_login import login_user, logout_user, current_user, login_required

from core.config import Config
from core.db_models import db, User, Itinerary, ItineraryDay, ItineraryActivity, login_manager
from core.forms import RegisterForm, LoginForm

from agent.gemini_agent import GeminiAgent
from services.rag_service import RAGService
from services.map_service import MapService

# Initialize the Flask core application infrastructure
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
    static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
)

app.config.from_object(Config)

# Register extensions with the app context
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

csrf = CSRFProtect(app)

# Instantiate core service layer dependencies
agent = GeminiAgent()
rag_service = RAGService()
map_service = MapService()


@app.route("/")
def index():
    """Renders the public landing platform page."""
    return render_template("index.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Manages unique user account creation transactions with built-in duplication checks."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegisterForm()
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            form.username.data = data.get('username')
            form.password.data = data.get('password')
            if 'csrf_token' in data:
                form.csrf_token.data = data.get('csrf_token')

        if form.validate_on_submit() or (request.is_json and form.validate()):
            username = form.username.data
            password = form.password.data

            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash("This username is already taken. Please choose another one.", "error")
            else:
                new_user = User(username=username)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for('dashboard'))
        else:
            flash("Registration validation failed. Please inspect your inputs.", "error")

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles secure user authentication sessions using WTForms and Flash alerts."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if request.method == 'POST':
        # Fallback mechanism to intercept JSON payloads from programmatic clients
        if request.is_json:
            data = request.get_json()
            form.username.data = data.get('username')
            form.password.data = data.get('password')
            if 'csrf_token' in data:
                form.csrf_token.data = data.get('csrf_token')

        if form.validate_on_submit() or (request.is_json and form.validate()):
            username = form.username.data
            password = form.password.data

            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                next_page = request.args.get('next') or url_for('dashboard')
                return redirect(next_page)
            else:
                flash("Invalid credentials. Please verify your username and password.", "error")
        else:
            flash("Form validation failed. Please check the required fields.", "error")
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """Terminates the current authenticated session and purges identity cookies."""
    logout_user()
    return redirect(url_for('index'))


@app.route("/dashboard")
@login_required
def dashboard():
    """Fetches and displays the central control panel with the user's historical itineraries."""
    my_itineraries = Itinerary.query.filter_by(user_id=current_user.id).order_by(Itinerary.created_at.desc()).all()
    return render_template("dashboard.html", username=current_user.username, itineraries=my_itineraries)


@app.route('/history')
@login_required
def history():
    """Lists saved travel logs mapped exclusively to the authenticated profile identity."""
    try:
        itineraries = Itinerary.query.filter_by(user_id=current_user.id).order_by(Itinerary.created_at.desc()).all()
        return render_template('history.html', itineraries=itineraries)
    except Exception as e:
        return render_template('history.html', itineraries=[], error=str(e))

@app.route("/generate_itinerary", methods=["POST"])
@login_required
def generate_itinerary():
    """Main orchestration endpoint managing the entire AI Agent RAG travel generation pipeline."""
    data = request.get_json() or {}

    city = data.get("city")
    duration = data.get("duration", 3)
    detected_interests = data.get("interests", [])

    if not city:
        return jsonify({
            "success": False,
            "message": "Target city name is mandatory to execute planning workflow."
        }), 400

    try:
        # Geocoding & Live OpenStreetMap POI collection via MapService
        lat, lon = map_service.get_coordinates(city)
        live_pois = map_service.fetch_live_pois(lat, lon, interests=detected_interests)

        if not live_pois:
            return jsonify({
                "success": False,
                "message": f"No active live destination points could be found for {city} matching interests."
            }), 404

        poi_lookup = {poi.poi_id: poi for poi in live_pois}

        # Context enrichment extracting local heuristics using the RAG index
        rag_context = rag_service.retrieve_relevant_context(city_name=city, interests=detected_interests)

        # Prompt synthesis and Gemini model transaction targeting structured schema blueprints
        itinerary_data = agent.generate_itinerary(
            city_name=city,
            total_days=duration,
            live_pois=live_pois,
            rag_context=rag_context,
            interests=detected_interests
        )

        #  Atomic database persistence ledger transactions
        new_itinerary = Itinerary(
            user_id=current_user.id,
            city=itinerary_data.city,
            title=itinerary_data.title,
            total_days=len(itinerary_data.days),
            interests=detected_interests,
            rag_context=itinerary_data.rag_context
        )
        db.session.add(new_itinerary)
        db.session.flush()

        for day_plan in itinerary_data.days:
            new_day = ItineraryDay(
                itinerary_id=new_itinerary.id,
                day_number=day_plan.day,
                notes=day_plan.notes
            )
            db.session.add(new_day)
            db.session.flush()

            slots = [
                ("morning", day_plan.morning),
                ("afternoon", day_plan.afternoon),
                ("evening", day_plan.evening)
            ]

            for slot_name, block_list in slots:
                for block in block_list:
                    poi_info = poi_lookup.get(block.poi_id)

                    activity = ItineraryActivity(
                        day_id=new_day.id,
                        slot=slot_name,
                        poi_id=block.poi_id,
                        name=poi_info.name if poi_info else "Unknown Destination",
                        category=poi_info.category if poi_info else "General",
                        why=block.why,
                        latitude=poi_info.lat if poi_info else None,
                        longitude=poi_info.lon if poi_info else None
                    )
                    db.session.add(activity)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Itinerary successfully coordinated, formatted, and persistent to storage.",
            "itinerary_id": new_itinerary.id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Engine failure: {str(e)}"
        }), 500
    

@app.route("/regenerate_itinerary", methods=["POST"])
@login_required
def regenerate_itinerary():
    """Re-orchestrates an existing travel plan by integrating iterative AI modifications based on user feedback."""

    data = request.get_json() or {}

    itinerary_id = data.get("itinerary_id")
    feedback = (data.get("feedback") or "").strip()
    new_interests = data.get("interests")
    new_duration = data.get("duration")

    if not itinerary_id:
        return jsonify({
            "success": False,
            "message": "Itinerary id is required."
        }), 400

    if not feedback:
        return jsonify({
            "success": False,
            "message": "Feedback cannot be empty."
        }), 400

    try:
        current_itinerary = Itinerary.query.filter_by(id=itinerary_id,user_id=current_user.id).first()

        if not current_itinerary:
            return jsonify({
                "success": False,
                "message": "Itinerary not found."
            }), 404

        city = current_itinerary.city
        interests = (new_interests if new_interests else current_itinerary.interests)
        duration = (int(new_duration) if new_duration else current_itinerary.total_days)

        lines = []

        for day in current_itinerary.days:
            lines.append(f"Day {day.day_number}")

            for act in day.activities:
                lines.append(
                    f"- {act.slot}: {act.name} ({act.category})"
                )

        old_itinerary_text = "\n".join(lines)


        lat, lon = map_service.get_coordinates(city)
        live_pois = map_service.fetch_live_pois(lat, lon, interests=interests)

        if not live_pois:
            return jsonify({
                "success": False,
                "message": f"No POIs found for {city}."
            }), 404

        poi_lookup = {poi.poi_id: poi for poi in live_pois}

        rag_context = rag_service.retrieve_relevant_context(city_name=city, interests=interests)

        itinerary_data = agent.regenerate_itinerary(
            city_name=city,
            total_days=duration,
            live_pois=live_pois,
            old_itinerary_text=old_itinerary_text,
            feedback=feedback,
            rag_context=rag_context,
            interests=interests
        )

        current_itinerary.days.clear()
        db.session.flush()

        current_itinerary.title = itinerary_data.title
        current_itinerary.rag_context = itinerary_data.rag_context
        current_itinerary.total_days = duration
        current_itinerary.interests = interests

        for day_plan in itinerary_data.days:

            new_day = ItineraryDay(
                itinerary_id=current_itinerary.id,
                day_number=day_plan.day,
                notes=day_plan.notes
            )

            db.session.add(new_day)
            db.session.flush()

            slots = {
                "morning": day_plan.morning,
                "afternoon": day_plan.afternoon,
                "evening": day_plan.evening
            }

            for slot_name, activities in slots.items():
                for block in activities:

                    poi = poi_lookup.get(block.poi_id)

                    activity = ItineraryActivity(
                        day_id=new_day.id,
                        slot=slot_name,
                        poi_id=block.poi_id,
                        name=poi.name if poi else "Unknown Destination",
                        category=poi.category if poi else "General",
                        why=block.why,
                        latitude=poi.lat if poi else None,
                        longitude=poi.lon if poi else None
                    )

                    db.session.add(activity)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Itinerary regenerated successfully.",
            "itinerary_id": current_itinerary.id
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route("/get_itinerary/<int:itinerary_id>")
@login_required
def get_itinerary(itinerary_id):
    """Fetches relational data blocks and coordinate records of a specific saved asset."""
    itinerary = Itinerary.query.filter_by(id=itinerary_id, user_id=current_user.id).first()
    if not itinerary:
        return jsonify({"success": False, "message": "Requested itinerary not found."}), 404

    result = {
        "title": itinerary.title,
        "city": itinerary.city,
        "total_days": itinerary.total_days,
        "interests": itinerary.interests,
        "rag_context": itinerary.rag_context,
        "days": []
    }

    for day in itinerary.days:
        day_data = {
            "day_number": day.day_number,
            "notes": day.notes,
            "activities": []
        }
        for act in day.activities:
            day_data["activities"].append({
                "slot": act.slot,
                "name": act.name,
                "category": act.category,
                "why": act.why,
                "lat": act.latitude,
                "lon": act.longitude
            })
        result["days"].append(day_data)

    return jsonify({"success": True, "data": result})

@app.route('/delete_itinerary/<int:itinerary_id>', methods=['DELETE'])
@login_required
def delete_itinerary(itinerary_id):
    """Performs cascading physical erasure of specified data nodes with security validation."""
    try:
        itinerary = db.session.get(Itinerary, itinerary_id)
        if not itinerary:
            return jsonify({"success": False, "message": "Itinerary structure not found."}), 404
            
        if itinerary.user_id != current_user.id:
            return jsonify({"success": False, "message": "Action forbidden: Resource ownership mismatch."}), 403
            
        db.session.delete(itinerary)
        db.session.commit()
        return jsonify({"success": True, "message": "Itinerary lineage successfully wiped."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Decommission workflow failed: {str(e)}"}), 500


if __name__ == "__main__":
    # with app.app_context():
    #    db.create_all()  # Ensure all database tables are created before the first request
    app.run(debug=True)