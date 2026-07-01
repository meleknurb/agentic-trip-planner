/* static/js/dashboard.js */

// GLOBAL STATE & CORE INSTANTIATION

let map = null;
let markersGroup = null;

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
    } else {
        map.setView([lat, lon], 13);
        markersGroup.clearLayers();
    }
}

// VIEW STATE MANAGEMENT & RUNTIME MUTATIONS

/**
Sets the dashboard UI to its default initial state when no data is loaded.
**/
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
 * Displays user-friendly, non-blocking asynchronous operational feedback inside the DOM.
 */
function renderFeedbackMessage(message) {
    // Check if an existing feedback element is present
    let feedbackElement = document.getElementById("runtimeFeedback");
    
    if (!feedbackElement) {
        feedbackElement = document.createElement("div");
        feedbackElement.id = "runtimeFeedback";
        
        // Append dynamically below the main action form
        const form = document.getElementById("itineraryForm");
        form.parentNode.insertBefore(feedbackElement, form.nextSibling);
    }
    
    feedbackElement.innerText = message;
    feedbackElement.className = "error-feedback";
    
    feedbackElement.classList.remove("hidden");
    
    // Smoothly fade out after 5 seconds
    setTimeout(() => {
        feedbackElement.classList.add("hidden");
    }, 5000);
}

// ASYNCHRONOUS DATA INGESTION & DOM RENDERING

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

            //  RAG Markdown Context Rendering Pipeline
            const ragBox = document.getElementById("ragBox");
            if (data.rag_context && data.rag_context.trim() !== "") {
                ragBox.innerHTML = marked.parse(data.rag_context);
            } else {
                ragBox.innerText = "No additional cultural guide notes found for this destination.";
            }
            
            // Main Structural Document Header Mutations
            document.getElementById("planTitle").innerText = data.title;
            document.getElementById("planMeta").innerText = `Destination City: ${data.city} | Total Duration: ${data.total_days} Days`;
            document.getElementById("mapTitle").innerText = `${data.city} Route Map`;

            // Dynamic Micro-Timeline Tree Parsing Loop
            const container = document.getElementById("daysContainer");
            container.innerHTML = "";

            let firstLat = null, firstLon = null;
            let bounds = [];

            data.days.forEach(day => {
                const dayBox = document.createElement("div");
                dayBox.className = "day-timeline-card";
                
                let dayHTML = `
                    <div class="timeline-dot"></div>
                    <h3>📅 Day ${day.day_number} Plan</h3>
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
                                bounds.push([latVal, lonVal]);
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
                            <p>Tips for the Day: ${day.notes}</p>
                        </div>
                    `;
                }

                dayBox.innerHTML = dayHTML;
                container.appendChild(dayBox);
            });

            // UI container must map to full view constraints before initializing map dimensions.
            loadingState.classList.add("hidden");
            itineraryContent.classList.remove("hidden");

            // Interactive Geospatial Node Deployment
            initMap(firstLat || 40.1885, firstLon || 29.0610);
            
            data.days.forEach(day => {
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
                    }
                });
            });

            // RECALIBRATE GEOSPATIAL VECTOR COMPASS: Prevents partial tile truncation artifacts.
            setTimeout(() => {
                if (map) {
                    map.invalidateSize();
                    if (bounds.length > 0) {
                        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
                    }
                }
            }, 100);

        } else {
            renderFeedbackMessage("Failed to retrieve route details: " + res.message);
            resetViewState();
        }
    } catch (err) {
        renderFeedbackMessage("An error occurred while building the route visual layout: " + err);
        resetViewState();
    }
}

// TRANSACTION ENGINE & FORM EVENT STREAM INTERCEPTORS

document.getElementById("itineraryForm").addEventListener("submit", async function(e) {
    e.preventDefault();
    
    const city = document.getElementById("city").value;
    const duration = parseInt(document.getElementById("duration").value);
    const token = document.querySelector('input[name="csrf_token"]').value;
    const checkedInterests = Array.from(document.querySelectorAll('input[name="interests"]:checked')).map(el => el.value);

    // Enter temporary micro-loading cycle
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
            // Instantly transition and project routing parameters without forcing template recalculation
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

// WINDOW LIFECYCLE DOM CONTENT INITIALIZATION TRIGGER

document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const itineraryId = urlParams.get('itinerary_id');
    
    if (itineraryId) {
        loadItineraryData(itineraryId);
    }
});