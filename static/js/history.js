/* static/js/history.js */

let map = null;

/**
 * Toggles the visibility of the cultural guide RAG container panel.
 */
function toggleRag() {
    const ragBox = document.getElementById("historyRagBox");
    if (ragBox) {
        ragBox.classList.toggle("hidden");
    }
}

/**
 * Resets the existing map instance from the DOM and initializes a clean Leaflet viewport.
 * @param {number} lat - Latitude coordinates.
 * @param {number} lon - Longitude coordinates.
 */
function resetAndInitHistoryMap(lat, lon) {
    const mapContainer = document.getElementById('historyMap');
    if (!mapContainer) return;

    // Destruct current map instance to prevent operational context memory leaks
    if (map !== null && map !== undefined) {
        map.off(); 
        map.remove(); 
        map = null;
    }

    // Initialize fresh map vector viewport
    map = L.map('historyMap').setView([lat, lon], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
}

/**
 * Asynchronously requests specific itinerary payloads via AJAX and builds the layout.
 * @param {string|number} id - Target itinerary unique database record identifier.
 */
async function loadRouteDetails(id) {
    // Dynamic Active UI Sidebar Card Tracking State
    document.querySelectorAll('.route-card').forEach(c => c.classList.remove('active-card'));
    document.getElementById(`route-${id}`)?.classList.add('active-card');

    const emptyState = document.getElementById("detailsEmptyState");
    const loadingState = document.getElementById("detailsLoadingState");
    const detailContent = document.getElementById("itineraryDetailContent");

    emptyState.classList.add("hidden");
    detailContent.classList.add("hidden");
    loadingState.classList.remove("hidden");

    try {
        const response = await fetch(`/get_itinerary/${id}`);
        const res = await response.json();

        if (res.success) {
            const data = res.data;

            // Cultural Knowledge Guide Markdown Parsing (RAG Layer Integration)
            const ragBox = document.getElementById("historyRagBox");
            if (data.rag_context && data.rag_context.trim() !== "") {
                ragBox.innerHTML = marked.parse(data.rag_context);
            } else {
                ragBox.innerText = "No additional cultural guide notes found for this destination.";
            }

            // Headings and Metadata Localization Updates
            document.getElementById("planTitle").innerText = data.title;
            document.getElementById("planMeta").innerText = `City: ${data.city} • Total Duration: ${data.total_days} Days`;
            document.getElementById("mapTitle").innerText = `${data.city} Route Map`;

            // Micro-Timeline Chronological Card Matrix Ingestion
            const container = document.getElementById("daysTimelineContainer");
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
                    { name: "🌅 Morning", key: "morning" },
                    { name: "☀️ Afternoon", key: "afternoon" },
                    { name: "🌙 Evening", key: "evening" }
                ];

                slots.forEach(slot => {
                    const acts = day.activities.filter(a => a.slot === slot.key);
                    dayHTML += `<div class="slot-column"><p class="slot-name">${slot.name}</p>`;
                    
                    if (acts.length > 0) {
                        acts.forEach(act => {
                            dayHTML += `
                                <div class="activity-item">
                                    <p class="act-name">📍 ${act.name}</p>
                                    <p class="act-why">💡 ${act.why}</p>
                                </div>
                            `;
                            
                            // Parse standard schema location coordinates safely
                            const latVal = parseFloat(act.lat);
                            const lonVal = parseFloat(act.lon);

                            if (!isNaN(latVal) && !isNaN(lonVal) && latVal !== 0 && lonVal !== 0) {
                                if (firstLat === null) { 
                                    firstLat = latVal; 
                                    firstLon = lonVal; 
                                    
                                }
                                bounds.push([latVal, lonVal]);
                            }
                        });
                    } else {
                        dayHTML += `<p class="no-activity-text">No activities scheduled.</p>`;
                    }
                    dayHTML += `</div>`;
                });

                dayHTML += `</div>`;

                if (day.notes) {
                    dayHTML += `
                        <div class="day-tips-box">
                            <p>Tips: ${day.notes}</p>
                        </div>
                    `;
                }

                dayBox.innerHTML = dayHTML;
                container.appendChild(dayBox);
            });

            // Toggle operational loader view overlays to viewable workspaces
            loadingState.classList.add("hidden");
            detailContent.classList.remove("hidden");

            // Geospatial Cluster Center Fallback Engine 
            const centerLat = firstLat || 39.9207; 
            const centerLon = firstLon || 32.8541;
            
            resetAndInitHistoryMap(centerLat, centerLon);

            // Populate Dynamic Map Markers Pipeline
            data.days.forEach(day => {
                day.activities.forEach(act => {
                    const latVal = parseFloat(act.lat);
                    const lonVal = parseFloat(act.lon);
                    
                    if (!isNaN(latVal) && !isNaN(lonVal) && latVal !== 0 && lonVal !== 0) {
                        const popupText = `
                            <div style="font-family:'Inter', sans-serif;">
                                <strong style="color:#0f172a;">📍 ${act.name}</strong>
                                <p style="color:#475569; font-size:11px; margin:4px 0 0 0; line-height:1.4;">${act.why}</p>
                            </div>
                        `;
                        L.marker([latVal, lonVal])
                         .addTo(map)
                         .bindPopup(popupText);
                    }
                });
            });

            // Asynchronous Map Structural Reflow Invalidation Layout
            setTimeout(() => {
                if (map) {
                    map.invalidateSize();
                    if (bounds.length > 0) {
                        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
                    }
                }
            }, 100);

        } else {
            console.error("Operational API Failure: " + res.message);
            resetToEmptyState();
        }
    } catch (err) {
        console.error("Network Ingestion Pipeline Error: " + err);
        resetToEmptyState();
    }
}

/**
 * Resets Workspace to default Empty Compass Welcome State.
 */
function resetToEmptyState() {
    document.getElementById("detailsLoadingState").classList.add("hidden");
    document.getElementById("itineraryDetailContent").classList.add("hidden");
    document.getElementById("detailsEmptyState").classList.remove("hidden");
    if (map) {
        map.remove();
        map = null;
    }
}

/**
 * Asynchronously drops a saved route record item immediately from history database context.
 * @param {Event} event - Native DOM Event object.
 * @param {string|number} id - Targeted itinerary identifier record node.
 */
async function deleteRoute(event, id) {
    // Block event bubbling pipeline to prevent triggering loadRouteDetails background execution
    event.stopPropagation();
    
    // Retrieve Application CSRF token securely straight from DOM Meta Layout Structure
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    try {
        const response = await fetch(`/delete_itinerary/${id}`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrfToken }
        });
        const result = await response.json();
        
        if (result.success) {
            // Smoothly eradicate components instantly without interruption dialogs
            document.getElementById(`route-${id}`).remove();
            resetToEmptyState();
            
            // Hard reload system layout matrix only if total stored archives count hits zero
            if (document.querySelectorAll('.route-card').length === 0) {
                location.reload();
            }
        } else {
            console.error("Backend Abort operational sequence error: " + result.message);
        }
    } catch (err) {
        console.error("Asynchronous deletion operation network crash: " + err);
    }
}