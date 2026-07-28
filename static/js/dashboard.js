// static/js/dashboard.js

// 1. GLOBAL STATE & CORE INSTANTIATION

let map = null;
let markersGroup = null;
let currentLoadedItineraryId = null; // Track current id globally for iterative updates
let currentItineraryData = null; // Cache the currently loaded itinerary data for filtering
let polylineGroup = null; // Route polyline layer group for dynamic updates
let filterControlInstance = null; // Holds the active Leaflet control instance for the day filter to prevent duplicate additions

/**
 * Initializes or updates the interactive Leaflet map instance.
 * Prevents initialization fragmentation and handles canvas size invalidation.
 */
function initMap(lat = 40.1885, lon = 29.0610) {
    if (!map) {
        map = L.map('map').setView([lat, lon], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        markersGroup = L.layerGroup().addTo(map);
        polylineGroup = L.layerGroup().addTo(map);
    } else {
        map.setView([lat, lon], 13);
        markersGroup.clearLayers();
        polylineGroup.clearLayers();
    }
}


// 2. VIEW STATE & UI FEEDBACK HELPERS

/**
 * Sets the dashboard UI to its default initial state when no data is loaded.
 */
function resetViewState() {
    document.getElementById("loadingState").classList.add("hidden");
    document.getElementById("itineraryContent").classList.add("hidden");
    document.getElementById("emptyState").classList.remove("hidden");            
}

/**
 * Toggles the visibility of the cultural guide RAG container panel.
 */
function toggleRag() {
    document.getElementById("ragBox").classList.toggle("hidden");
}

/**
 * Toggles the visibility of the iterative AI regeneration input area.
 */
function toggleRegenBox() {
    const regenBox = document.getElementById("regenBox");
    if (regenBox) {
        regenBox.classList.toggle("hidden");
    }
}

/**
 * Toggles the visibility of the single-day regeneration input box for a specific day.
 */
function toggleSingleDayRegenBox(dayNumber) {
    const box = document.getElementById(`singleRegenBox-${dayNumber}`);
    if (box) {
        box.classList.toggle("hidden");
    }
}

/**
 * Displays user-friendly, non-blocking asynchronous operational feedback inside the DOM.
 */
function renderFeedbackMessage(message) {
    let feedbackElement = document.getElementById("runtimeFeedback");
    
    if (!feedbackElement) {
        feedbackElement = document.createElement("div");
        feedbackElement.id = "runtimeFeedback";
        const form = document.getElementById("itineraryForm");
        form.parentNode.insertBefore(feedbackElement, form.nextSibling);
    }
    
    feedbackElement.innerText = message;
    feedbackElement.className = "error-feedback";
    feedbackElement.classList.remove("hidden");
    
    setTimeout(() => {
        feedbackElement.classList.add("hidden");
    }, 5000);
}


// 3. MAP FILTERING & CONTROL LOGIC

/**
 * Filters the map markers and polylines based on the selected day value.
 */
function filterMapByDay(dayVal) {
    if (!markersGroup || !polylineGroup || !currentItineraryData) return;

    markersGroup.clearLayers();
    polylineGroup.clearLayers();
    let bounds = [];

    currentItineraryData.days.forEach(day => {
        if (dayVal === "all" || parseInt(dayVal) === day.day_number) {
            let dayLatLngs = [];

            day.activities.forEach(act => {
                const latVal = parseFloat(act.lat);
                const lonVal = parseFloat(act.lon);

                if (!isNaN(latVal) && !isNaN(lonVal) && latVal !== 0 && lonVal !== 0) {
                    const popupText = `
                        <div class="map-popup-container">
                            <strong style="color:#0f172a; font-size:0.85rem;">📍 ${act.name}</strong>
                            <p style="color:#475569; font-size:0.75rem; margin:4px 0 0 0; line-height:1.4;">${act.why}</p>
                        </div>
                    `;
                    L.marker([latVal, lonVal])
                     .addTo(markersGroup)
                     .bindPopup(popupText);

                    dayLatLngs.push([latVal, lonVal]);
                    bounds.push([latVal, lonVal]);
                }
            });

            if (dayVal !== "all" && dayLatLngs.length > 1) {
                L.polyline(dayLatLngs, {
                    color: '#054882',      
                    weight: 4,              
                    opacity: 0.75,         
                    dashArray: '6, 8' 
                }).addTo(polylineGroup);
            }
        }
    });
    
    if (bounds.length > 0 && map) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }
}

/**
 * Rebuilds the Leaflet day filter control every time the itinerary changes.
 */
function addMapFilterControl() {
    if (!map) return;

    if (filterControlInstance) {
        map.removeControl(filterControlInstance);
        filterControlInstance = null;
    }

    const FilterControl = L.Control.extend({
        options: {
            position: "topright"
        },
        onAdd: function () {
            const wrapper = L.DomUtil.create("div", "map-filter-control");

            wrapper.innerHTML = `
                <div class="custom-select">
                    <div class="select-trigger">
                        <span class="filter-icon">📅</span>
                        All Days
                    </div>
                    <div class="select-options" id="leafletMapDayOptions">
                        <div class="select-option" data-value="all">
                            All Days
                        </div>
                    </div>
                </div>
            `;

            const optionsContainer = wrapper.querySelector("#leafletMapDayOptions");

            if (currentItineraryData && currentItineraryData.days) {
                currentItineraryData.days.forEach(day => {
                    const option = document.createElement("div");
                    option.className = "select-option";
                    option.dataset.value = day.day_number;
                    option.textContent = `Day ${day.day_number}`;
                    optionsContainer.appendChild(option);
                });
            }

            wrapper.addEventListener("click", function (e) {
                const custom = wrapper.querySelector(".custom-select");

                if (e.target.classList.contains("select-option")) {
                    const value = e.target.dataset.value;
                    wrapper.querySelector(".select-trigger").innerHTML =
                        `<span class="filter-icon">📅</span> ${e.target.textContent}`;
                    filterMapByDay(value);
                    custom.classList.remove("active");
                } else {
                    custom.classList.toggle("active");
                }
            });

            L.DomEvent.disableClickPropagation(wrapper);
            L.DomEvent.disableScrollPropagation(wrapper);

            return wrapper;
        }
    });

    filterControlInstance = new FilterControl();
    map.addControl(filterControlInstance);
}


// 4. MAIN DATA INGESTION & DOM RENDERING

/**
 * Fetches targeted itinerary records from the backend API core architectures
 * and maps the downstream array nodes directly into the user interface timeline framework.
 */
async function loadItineraryData(id) {
    const emptyState = document.getElementById("emptyState");
    const itineraryContent = document.getElementById("itineraryContent");
    const loadingState = document.getElementById("loadingState");

    emptyState.classList.add("hidden");
    itineraryContent.classList.add("hidden");
    loadingState.classList.remove("hidden");

    try {
        const response = await fetch(`/get_itinerary/${id}`);
        const res = await response.json();

        if (res.success) {
            const data = res.data;

            if (data.days && Array.isArray(data.days)) {
                data.days.sort((a, b) => a.day_number - b.day_number);
            }

            currentItineraryData = data;
            
            // Auto-populate sidebar form fields with fetched itinerary data to preserve UX state.
            const cityInput = document.getElementById("city");
            if (cityInput && data.city) {
                cityInput.value = data.city;
            }

            const durationInput = document.getElementById("duration");
            if (durationInput && data.total_days) {
                durationInput.value = data.total_days;
            }

            if (data.interests && Array.isArray(data.interests)) {
                const checkboxes = document.querySelectorAll('input[name="interests"]');
                checkboxes.forEach(checkbox => {
                    if (data.interests.includes(checkbox.value)) {
                        checkbox.checked = true;
                    } else {
                        checkbox.checked = false;
                    }
                });
            }

            currentLoadedItineraryId = id;

            const feedbackInput = document.getElementById("regenFeedback");
            if (feedbackInput) feedbackInput.value = "";
            const regenBox = document.getElementById("regenBox");
            if (regenBox) regenBox.classList.add("hidden");

            const ragBox = document.getElementById("ragBox");
            if (data.rag_context && data.rag_context.trim() !== "") {
                ragBox.innerHTML = marked.parse(data.rag_context);
            } else {
                ragBox.innerText = "No additional cultural guide notes found for this destination.";
            }
            
            document.getElementById("planTitle").innerText = data.title;
            document.getElementById("planMeta").innerText = `Destination City: ${data.city} | Total Duration: ${data.total_days} Days`;
            document.getElementById("mapTitle").innerText = `${data.city} Route Map`;

            const container = document.getElementById("daysContainer");
            container.innerHTML = "";

            let firstLat = null, firstLon = null;

            data.days.forEach(day => {
                const dayBox = document.createElement("div");
                dayBox.className = "day-timeline-card";
                
                let dayHTML = `
                    <div class="timeline-dot"></div>
                    <div class="day-header-row">
                        <h3>📅 Day ${day.day_number} Plan</h3>
                        <button onclick="toggleSingleDayRegenBox(${day.day_number})" class="single-day-toggle-btn">
                            🔄 Change This Day
                        </button>
                    </div>

                    <div id="singleRegenBox-${day.day_number}" class="single-regen-box hidden">
                        <textarea id="singleFeedback-${day.day_number}" placeholder="What would you like to change for Day ${day.day_number}?"></textarea>
                        <div class="single-regen-actions">
                            <button onclick="submitSingleDayRegeneration(${day.day_number})" class="single-day-submit-btn">
                                Apply Day ${day.day_number} Update
                            </button>
                        </div>
                    </div>

                    <div class="slots-grid">
                `;

                const slots = [
                    { name: "🌅 Morning Activity", key: "morning" },
                    { name: "☀️ Afternoon Plan", key: "afternoon" },
                    { name: "🌙 Evening & Night", key: "evening" }
                ];

                slots.forEach(slot => {
                    const acts = day.activities.filter(a => a.slot === slot.key);
                    dayHTML += `
                        <div class="slot-column">
                            <p class="slot-name">${slot.name}</p>
                    `;
                    
                    if (acts.length > 0) {
                        acts.forEach(act => {
                            dayHTML += `
                                <div class="activity-item">
                                    <p class="act-name">📍 ${act.name}</p>
                                    <p class="act-why">💡 ${act.why}</p>
                                </div>
                            `;
                            
                            const latVal = parseFloat(act.lat);
                            const lonVal = parseFloat(act.lon);

                            if (!isNaN(latVal) && !isNaN(lonVal) && latVal !== 0 && lonVal !== 0) {
                                if (!firstLat) { firstLat = latVal; firstLon = lonVal; }
                            }
                        });
                    } else {
                        dayHTML += `<p class="no-activity-text">No scheduled activities for this time.</p>`;
                    }
                    dayHTML += `</div>`;
                });

                dayHTML += `</div>`;

                if (day.notes) {
                    dayHTML += `
                        <div class="day-tips-box">
                            <p>Tips for the day: ${day.notes}</p>
                        </div>
                    `;
                }

                dayBox.innerHTML = dayHTML;
                container.appendChild(dayBox);
            });

            loadingState.classList.add("hidden");
            itineraryContent.classList.remove("hidden");

            initMap(firstLat || 40.1885, firstLon || 29.0610);
            addMapFilterControl();
            filterMapByDay("all");

        } else {
            renderFeedbackMessage("Failed to retrieve route details: " + res.message);
            resetViewState();
        }
    } catch (err) {
        renderFeedbackMessage("An error occurred while building the route visual layout: " + err);
        resetViewState();
    }
}

// 5. API REQUEST ACTIONS & FORM EVENT HANDLERS

/**
 * Dispatches a revision feedback request to the iterative AI agent pipeline.
 * Repaints the visual canvas asynchronously without breaking map contexts.
 */
async function submitPlanRegeneration() {
    const feedbackText = document.getElementById("regenFeedback").value.trim();
    const submitBtn = document.getElementById("submitRegenBtn");

    if (!feedbackText) {
        alert("Please specify what you would like the AI to change before applying adjustments.");
        return;
    }

    if (!currentLoadedItineraryId) {
        renderFeedbackMessage("No active itinerary reference target discovered to direct updates.");
        return;
    }

    const checkedInterests = [];
    document.querySelectorAll('input[name="interests"]:checked').forEach(cb => {
        checkedInterests.push(cb.value);
    });

    const durationSelectElement = document.getElementById("duration");
    const duration = durationSelectElement ? durationSelectElement.value : null;

    submitBtn.disabled = true;
    submitBtn.innerText = "Rebuilding Plan... ⏳";
    
    document.getElementById("itineraryContent").classList.add("hidden");
    document.getElementById("loadingState").classList.remove("hidden");

    const csrfTokenElement = document.querySelector('input[name="csrf_token"]');
    const token = csrfTokenElement ? csrfTokenElement.value : "";

    try {
        const response = await fetch("/regenerate_itinerary", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": token
            },
            body: JSON.stringify({ 
                itinerary_id: currentLoadedItineraryId, 
                feedback: feedbackText,
                interests: checkedInterests,
                duration: duration
            })
        });

        const result = await response.json();

        if (result.success) {
            await loadItineraryData(result.itinerary_id);
        } else {
            renderFeedbackMessage(`AI Regeneration failed: ${result.message || 'Unknown internal service exception.'}`);
            document.getElementById("loadingState").classList.add("hidden");
            document.getElementById("itineraryContent").classList.remove("hidden");
        }
    } catch (err) {
        renderFeedbackMessage("A network failure occurred during iterative reconstruction: " + err);
        document.getElementById("loadingState").classList.add("hidden");
        document.getElementById("itineraryContent").classList.remove("hidden");
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = "Apply Adjustments";
    }
}

/**
 * Dispatches a single-day revision feedback request to the backend API pipeline.
 */
async function submitSingleDayRegeneration(dayNumber) {
    const feedbackInput = document.getElementById(`singleFeedback-${dayNumber}`);
    const feedbackText = feedbackInput ? feedbackInput.value.trim() : "";
    
    if (!feedbackText) {
        alert(`Please specify what you would like to change for Day ${dayNumber}.`);
        return;
    }

    if (!currentLoadedItineraryId) {
        renderFeedbackMessage("No active itinerary reference target discovered.");
        return;
    }

    const checkedInterests = [];
    document.querySelectorAll('input[name="interests"]:checked').forEach(cb => {
        checkedInterests.push(cb.value);
    });

    const csrfTokenElement = document.querySelector('input[name="csrf_token"]');
    const token = csrfTokenElement ? csrfTokenElement.value : "";

    document.getElementById("itineraryContent").classList.add("hidden");
    document.getElementById("loadingState").classList.remove("hidden");

    try {
        const response = await fetch("/regenerate_single_day", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": token
            },
            body: JSON.stringify({
                itinerary_id: currentLoadedItineraryId,
                day_number: dayNumber,
                feedback: feedbackText,
                interests: checkedInterests
            })
        });

        const result = await response.json();

        if (result.success) {
            await loadItineraryData(currentLoadedItineraryId);
            renderFeedbackMessage(result.message);
        } else {
            renderFeedbackMessage(`Single day regeneration failed: ${result.message}`);
            document.getElementById("loadingState").classList.add("hidden");
            document.getElementById("itineraryContent").classList.remove("hidden");
        }
    } catch (err) {
        renderFeedbackMessage("A network failure occurred during single-day update: " + err);
        document.getElementById("loadingState").classList.add("hidden");
        document.getElementById("itineraryContent").classList.remove("hidden");
    }
}

// 6. EVENT LISTENERS & LIFECYCLE HOOKS

document.getElementById("itineraryForm").addEventListener("submit", async function(e) {
    e.preventDefault();
    
    const city = document.getElementById("city").value;
    const duration = parseInt(document.getElementById("duration").value);
    const token = document.querySelector('input[name="csrf_token"]').value;
    const checkedInterests = Array.from(document.querySelectorAll('input[name="interests"]:checked')).map(el => el.value);

    document.getElementById("emptyState").classList.add("hidden");
    document.getElementById("itineraryContent").classList.add("hidden");
    document.getElementById("loadingState").classList.remove("hidden");
    document.getElementById("generateBtn").disabled = true;

    try {
        const response = await fetch("/generate_itinerary", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": token
            },
            body: JSON.stringify({ city, duration, interests: checkedInterests })
        });

        const result = await response.json();
        
        if (result.success) {
            await loadItineraryData(result.itinerary_id);
            const newUrl = `${window.location.pathname}?itinerary_id=${result.itinerary_id}`;
            window.history.pushState({ path: newUrl }, '', newUrl);
        } else {
            renderFeedbackMessage(`No destinations found for "${city}". The area might be too large (e.g. state/country) or servers are busy. Please try a specific city.`);
            resetViewState();
        }
    } catch (err) {
        renderFeedbackMessage("A critical system exception occurred: " + err);
        resetViewState();
    } finally {
        document.getElementById("generateBtn").disabled = false;
    }
});

document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const itineraryId = urlParams.get('itinerary_id');
    
    if (itineraryId) {
        loadItineraryData(itineraryId);
    }
});