# app.py

import os
import json
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.csrf import CSRFProtect
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.exceptions import BadRequest

from core.config import Config
from core.db_models import db, User, Itinerary, ItineraryDay, ItineraryActivity, Feedback, login_manager
from core.forms import RegisterForm, LoginForm, UpdatePasswordForm

from agent.gemini_agent import GeminiAgent
from services.rag_service import RAGService
from services.map_service import MapService
from services.feedback_service import FeedbackService

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
feedback_service = FeedbackService()

# Define a set of valid interests for user selection and itinerary generation
VALID_INTERESTS = {"history","museums","scenic","food","coffee","outdoors","nightlife","shopping","entertainment"}

# Define a minimum threshold for the number of POIs required to generate a valid itinerary
MIN_REQUIRED_POIS = 5

# Error handler for malformed JSON requests
@app.errorhandler(BadRequest)
def handle_bad_request(e):
    """Return JSON instead of HTML for malformed client requests."""

    if request.is_json:
        message = "Malformed JSON request. Please check the request body and try again."
    else:
        message = "Bad request."

    return jsonify({
        "success": False,
        "message": message
    }), 400

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
    city = data.get("city", "").strip()

    if not city:
        return jsonify({
         "success": False,
            "message": "Target city name is mandatory to execute planning workflow."
        }), 400

    try:
        duration = int(data.get("duration", 3))
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Duration must be a valid number."
        }), 400

    if duration < 1 or duration > 7:
        return jsonify({
            "success": False,
            "message": "Duration must be between 1 and 7 days."
        }), 400

    detected_interests = data.get("interests", [])

    if not isinstance(detected_interests, list):
        return jsonify({
            "success": False,
            "message": "Interests must be provided as a list."
        }), 400

    if not detected_interests:
        return jsonify({
            "success": False,
            "message": "Please select at least one interest category."
        }), 400

    invalid_interests = [interest for interest in detected_interests if interest not in VALID_INTERESTS]

    if invalid_interests:
        return jsonify({
            "success": False,
            "message": f"Invalid interest categories: {', '.join(invalid_interests)}."
        }), 400
    
    try:
        user_prefs = {
            'pace': current_user.travel_pace,
            'diet': current_user.dietary_preference
        }

        boost_scores = feedback_service.calculate_boost_scores(city.lower())

        # Geocoding & Live OpenStreetMap POI collection via MapService
        try:
            lat, lon = map_service.get_coordinates(city)

        except ValueError as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 404

        except RuntimeError:
            return jsonify({
                "success": False,
                "message": "The geocoding service is temporarily unavailable. Please try again later."
            }), 503

        try:
            live_pois = map_service.fetch_live_pois(lat, lon, interests=detected_interests, dietary=user_prefs['diet'],boost_scores=boost_scores)

        except RuntimeError:
            return jsonify({
                "success": False,
                "message": "The POI service is temporarily unavailable. Please try again later."
            }), 503

        if len(live_pois) < MIN_REQUIRED_POIS:
            return jsonify({
                "success": False,
                "message": (
                    "Unfortunately, there aren't enough places matching your selected "
                    "interests in this destination. Please try different interests or "
                    "a larger city."
                )
            }), 422

        poi_lookup = {poi.poi_id: poi for poi in live_pois}

        # Context enrichment extracting local heuristics using the RAG index
        rag_context = rag_service.retrieve_relevant_context(city_name=city, interests=detected_interests, pace=user_prefs['pace'], dietary=user_prefs['diet'])

        # Prompt synthesis and Gemini model transaction targeting structured schema blueprints
        try:
            itinerary_data = agent.generate_itinerary(
                city_name=city,
                total_days=duration,
                live_pois=live_pois,
                rag_context=rag_context,
                interests=detected_interests,
                user_preferences=user_prefs
            )
        except RuntimeError as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 503

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
            "message": "Itinerary generated successfully",
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

    # Duration (only if the user supplied a new value)
    if new_duration is not None:
        try:
            new_duration = int(new_duration)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Duration must be a valid number."
            }), 400

        if not 1 <= new_duration <= 7:
            return jsonify({
                "success": False,
                "message": "Duration must be between 1 and 7 days."
            }), 400

    # Interests (only if the user supplied them)
    if new_interests is not None:

        if not isinstance(new_interests, list):
            return jsonify({
                "success": False,
                "message": "Interests must be provided as a list."
            }), 400

        if not new_interests:
            return jsonify({
                "success": False,
                "message": "Please select at least one interest category."
            }), 400

        invalid_interests = [interest for interest in new_interests if interest not in VALID_INTERESTS]

        if invalid_interests:
            return jsonify({
                "success": False,
                "message": f"Invalid interest categories: {', '.join(invalid_interests)}."
            }), 400

    try:
        current_itinerary = Itinerary.query.filter_by(id=itinerary_id,user_id=current_user.id).first()

        if not current_itinerary:
            return jsonify({
                "success": False,
                "message": "Itinerary not found."
            }), 404

        user_prefs = {
            'pace': current_user.travel_pace or 'balanced',
            'diet': current_user.dietary_preference or 'omnivore'
        }

        city = current_itinerary.city
        interests = new_interests if new_interests is not None else current_itinerary.interests
        duration = new_duration if new_duration is not None else current_itinerary.total_days

        lines = []

        for day in current_itinerary.days:
            lines.append(f"Day {day.day_number}")

            for act in day.activities:
                lines.append(
                    f"- {act.slot}: {act.name} ({act.category})"
                )

        old_itinerary_text = "\n".join(lines)

        boost_scores = feedback_service.calculate_boost_scores(city.lower())

        try:
            lat, lon = map_service.get_coordinates(city)

        except ValueError as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 404
        
        except RuntimeError:
            return jsonify({
                "success": False,
                "message": "The geocoding service is temporarily unavailable. Please try again later."
            }), 503

        try:
            live_pois = map_service.fetch_live_pois(lat, lon, interests=interests, dietary=user_prefs['diet'],boost_scores=boost_scores)

        except RuntimeError:
            return jsonify({
                "success": False,
                "message": "The POI service is temporarily unavailable. Please try again later."
            }), 503

        if len(live_pois) < MIN_REQUIRED_POIS:
            return jsonify({
                "success": False,
                "message": (
                    "Unfortunately, there aren't enough places matching your selected "
                    "interests in this destination. Please try different interests or "
                    "a larger city."
                )
            }), 422

        poi_lookup = {poi.poi_id: poi for poi in live_pois}

        rag_context = rag_service.retrieve_relevant_context(city_name=city, interests=interests, pace=user_prefs['pace'], dietary=user_prefs['diet'])

        try:
            itinerary_data = agent.regenerate_itinerary(
                city_name=city,
                total_days=duration,
                live_pois=live_pois,
                old_itinerary_text=old_itinerary_text,
                feedback=feedback,
                rag_context=rag_context,
                interests=interests,
                user_preferences=user_prefs
            )
        except RuntimeError as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 503

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

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "An unexpected error occurred while regenerating the itinerary."
        }), 500

@app.route("/regenerate_single_day", methods=["POST"])
@login_required
def regenerate_single_day():
    """Regenerates only one day of an itinerary while preserving the rest of the trip."""

    data = request.get_json() or {}

    itinerary_id = data.get("itinerary_id")
    feedback = (data.get("feedback") or "").strip()

    try:
        day_number = int(data.get("day_number"))
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Day number must be a valid number."
        }), 400

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

    if day_number < 1:
        return jsonify({
            "success": False,
            "message": "Day number must be greater than zero."
        }), 400

    try:
        current_itinerary = Itinerary.query.filter_by(id=itinerary_id,user_id=current_user.id).first()

        if not current_itinerary:
            return jsonify({
                "success": False,
                "message": "Itinerary not found."
            }), 404

        if day_number > current_itinerary.total_days:
            return jsonify({
                "success": False,
                "message": f"Day number cannot exceed the total duration of the itinerary ({current_itinerary.total_days} days)."
            }), 400

        target_day_obj = ItineraryDay.query.filter_by(itinerary_id=current_itinerary.id,day_number=day_number).first()

        if not target_day_obj:
            return jsonify({
                "success": False,
                "message": "Specified day not found in this itinerary."
            }), 404

        # User preferences
        user_prefs = {
            "pace": current_user.travel_pace or "balanced",
            "diet": current_user.dietary_preference or "omnivore"
        }

        city = current_itinerary.city
        interests = current_itinerary.interests
        total_days = current_itinerary.total_days

        # Build current day's text
        old_day_lines = [f"Day {day_number} (Notes: {target_day_obj.notes})"]

        for act in target_day_obj.activities:
            old_day_lines.append(f"- {act.slot}: {act.name} ({act.category}) - Why: {act.why}")

        old_day_text = "\n".join(old_day_lines)

        # Build summary of other days to avoid duplicates
        other_days_activities = []

        for day in current_itinerary.days:
            if day.day_number != day_number:
                for act in day.activities:
                    other_days_activities.append(act.name)

        other_days_summary = (", ".join(other_days_activities) if other_days_activities else "None")

        boost_scores = feedback_service.calculate_boost_scores(city.lower())

        # Fetch POIs using ORIGINAL itinerary interests
        try:
            lat, lon = map_service.get_coordinates(city)

        except ValueError as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 404
        
        except RuntimeError:
            return jsonify({
                "success": False,
                "message": "The geocoding service is temporarily unavailable. Please try again later."
            }), 503

        try:
            live_pois = map_service.fetch_live_pois(lat,lon,interests=interests,dietary=user_prefs["diet"],boost_scores=boost_scores)

        except RuntimeError:
            return jsonify({
                "success": False,
                "message": "The POI service is temporarily unavailable. Please try again later."
            }), 503

        if len(live_pois) < MIN_REQUIRED_POIS:
            return jsonify({
                "success": False,
                "message": (
                    "Unfortunately, there aren't enough places matching your selected "
                    "interests in this destination. Please try different interests or "
                    "a larger city."
                )
            }), 422

        poi_lookup = {poi.poi_id: poi for poi in live_pois}

        # Preserve existing RAG context
        rag_context = current_itinerary.rag_context

        try:
            itinerary_data = agent.regenerate_single_day(
                city_name=city,
                target_day_number=day_number,
                total_days=total_days,
                live_pois=live_pois,
                old_day_text=old_day_text,
                feedback=feedback,
                rag_context=rag_context,
                interests=interests,
                user_preferences=user_prefs,
                other_days_summary=other_days_summary
            )
        except RuntimeError as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 503

        # Replace ONLY the selected day
        updated = False
        for day_plan in itinerary_data.days:

            if day_plan.day != day_number:
                continue

            updated = True

            ItineraryActivity.query.filter_by(day_id=target_day_obj.id).delete()

            target_day_obj.notes = day_plan.notes

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
                        day_id=target_day_obj.id,
                        slot=slot_name,
                        poi_id=block.poi_id,
                        name=poi.name if poi else "Unknown Destination",
                        category=poi.category if poi else "General",
                        why=block.why,
                        latitude=poi.lat if poi else None,
                        longitude=poi.lon if poi else None
                    )

                    db.session.add(activity)

            break

        if not updated:
            raise RuntimeError("Gemini did not return the requested day.")

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Day {day_number} regenerated successfully.",
            "itinerary_id": current_itinerary.id
        })

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "An unexpected error occurred while regenerating the itinerary."
        }), 500

@app.route("/get_itinerary/<int:itinerary_id>")
@login_required
def get_itinerary(itinerary_id):
    """Fetches relational data blocks and coordinate records of a specific saved asset."""
    itinerary = Itinerary.query.filter_by(id=itinerary_id, user_id=current_user.id).first()
    if not itinerary:
        return jsonify({"success": False, "message": "Requested itinerary not found."}), 404

    feedback_stats = feedback_service.get_feedback_statistics(itinerary.city)

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
                "poi_id": act.poi_id,
                "name": act.name,
                "category": act.category,
                "why": act.why,
                "lat": act.latitude,
                "lon": act.longitude
            })
        result["days"].append(day_data)

    return jsonify({"success": True, "data": result, "feedback_stats": feedback_stats})

@app.route("/submit_poi_feedback", methods=["POST"])
@login_required
def submit_poi_feedback():

    data = request.get_json() or {}

    city = data.get("city")
    poi_id = data.get("poi_id")
    vote = data.get("vote")

    if not city or not poi_id or vote not in ["up", "down"]:
        return jsonify({
            "success": False,
            "message": "Invalid feedback."
        }), 400

    try:

        feedback_event = {
            "ts": time.time(),
            "city_key": city.lower().strip(),
            "poi_id": poi_id,
            "vote": vote
        }

        feedback_path = os.path.join("feedback", "poi_feedback.jsonl")

        os.makedirs("feedback", exist_ok=True)

        with open(feedback_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_event))
            f.write("\n")

        return jsonify({
            "success": True,
            "message": "Feedback saved."
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

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
        return jsonify({"success": True, "message": "Itinerary deleted successfully."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Decommission workflow failed: {str(e)}"}), 500

@app.route('/settings', methods=['GET'])
@login_required
def settings():
    """Renders the settings workspace dynamically checking the URL parameters for focus states."""
    password_form = UpdatePasswordForm()
    active_tab = request.args.get('tab', 'profile')
    
    return render_template('settings.html', password_form=password_form, active_tab=active_tab)

@app.route('/settings/profile', methods=['POST'])
@login_required
def settings_profile():
    """Handles independent username updates and redirects strictly back to the profile tab."""
    new_username = request.form.get('username', '').strip()
    
    if not new_username:
        flash("Username cannot be empty.", "error")
        return redirect(url_for('settings', tab='profile'))

    existing_user = User.query.filter(User.username == new_username, User.id != current_user.id).first()
    if existing_user:
        flash("This username is already taken. Please choose another one.", "error")
        return redirect(url_for('settings', tab='profile'))
        
    try:
        db_user = db.session.get(User, current_user.id)
        if db_user:
            db_user.username = new_username
            db.session.commit()
            db.session.refresh(db_user)
            flash("Username updated successfully!", "success")
        else:
            flash("User context not found in database.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {str(e)}", "error")
        
    return redirect(url_for('settings', tab='profile'))

@app.route('/settings/password', methods=['POST'])
@login_required
def settings_password():
    """Handles isolated user credential updates and preserves focus on the security tab upon error."""
    form = UpdatePasswordForm()

    if form.validate_on_submit():
        current_password = form.current_password.data
        new_password = form.new_password.data
        confirm_password = form.confirm_new_password.data
        
        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
            return render_template('settings.html', password_form=form, active_tab='security')
            
        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return render_template('settings.html', password_form=form, active_tab='security')
            
        try:
            db_user = db.session.get(User, current_user.id)
            if db_user:
                db_user.set_password(new_password)
                db.session.commit()
                flash("Password updated successfully!", "success")
                return redirect(url_for('settings', tab='security'))
            else:
                flash("User context not found in database.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "error")
            return render_template('settings.html', password_form=form, active_tab='security')
    else:
        flash("Form validation failed. Please check your password fields.", "error")
        return render_template('settings.html', password_form=form, active_tab='security')
        
    return redirect(url_for('settings', tab='security'))


@app.route('/settings/ai-preferences', methods=['POST'])
@login_required
def settings_ai_preferences():
    current_user.travel_pace = request.form.get('default_pace')
    current_user.dietary_preference = request.form.get('dietary')
    db.session.commit()
    flash("Preferences saved!", "success")
    return redirect(url_for('settings', tab='ai-preferences'))

@app.route('/delete_account', methods=['GET'])
@login_required
def delete_account():
    user = current_user._get_current_object()
    logout_user()

    db.session.delete(user)
    db.session.commit()

    return redirect(url_for('index'))

@app.route('/submit_feedback', methods=['POST'])
@login_required
def submit_feedback():
    message = request.form.get('message')
    f_type = request.form.get('feedback_type')

    if not message:
        flash("Message cannot be empty.", "error")
        return redirect(url_for('settings', tab='feedback'))
    
    new_feedback = Feedback(user_id=current_user.id, message=message, feedback_type=f_type)
    
    db.session.add(new_feedback)
    db.session.commit()
    
    flash('Thank you for you feedback!', 'success')
    return redirect(url_for('settings', tab='feedback'))

if __name__ == "__main__":
    # with app.app_context():
    #    db.create_all()  # Ensure all database tables are created before the first request
    app.run(debug=True)