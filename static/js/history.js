/* static/js/history.js */

let map = null;
let currentItineraryId = null;
let currentItineraryData = null;
let markersGroup = null;
let polylineGroup = null;
let filterControlInstance = null;

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

    if (map !== null && map !== undefined) {
        map.off(); 
        map.remove(); 
        map = null;
    }

    map = L.map('historyMap').setView([lat, lon], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    markersGroup = L.layerGroup().addTo(map);
    polylineGroup = L.layerGroup().addTo(map);
}

/**
 * Asynchronously requests specific itinerary payloads via AJAX and builds the layout.
 * @param {string|number} id - Target itinerary unique database record identifier.
 */
async function loadRouteDetails(id) {
    currentItineraryId = id;
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
            currentItineraryData = data;

            // Cultural Knowledge Guide Markdown Parsing (RAG Layer Integration)
            const ragBox = document.getElementById("historyRagBox");
            if (data.rag_context && data.rag_context.trim() !== "") {
                ragBox.innerHTML = marked.parse(data.rag_context);
            } else {
                ragBox.innerText = "No additional cultural guide notes found for this destination.";
            }

            const dayOptionsContainer = document.getElementById("historyMapDayOptions");
            dayOptionsContainer.innerHTML = '<div class="select-option" data-value="all">All Days</div>';
            
            data.days.forEach(day => {
                const optDiv = document.createElement("div");
                optDiv.className = "select-option";
                optDiv.setAttribute("data-value", day.day_number);
                optDiv.innerText = `Day ${day.day_number}`;
                dayOptionsContainer.appendChild(optDiv);
            });

            // Reset the filter dropdown value to "All Days"
            const trigger = document.querySelector('#historyMapDayFilterContainer .select-trigger');
            if (trigger) {
                trigger.innerHTML = `<span class="filter-icon">📅</span> All Days`;
            }
            const hiddenInput = document.getElementById("historyMapDayValue");
            if (hiddenInput) {
                hiddenInput.value = "all";
            }

            // Headings and Metadata Localization Updates
            document.getElementById("planTitle").innerText = data.title;

            const formattedInterests = data.interests ? data.interests.map(i => i.charAt(0).toUpperCase() + i.slice(1)).join(', ') : '';
            document.getElementById("planMeta").innerText = `City: ${data.city} • Total Duration: ${data.total_days} Days${formattedInterests ? ` • Interests: ${formattedInterests}` : ''}`;
            
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

            // Add the day filter dropdown into the Leaflet map's top-right corner natively
            addHistoryMapFilterControl();

            // Initial render of all markers and polylines via the filter function
            filterHistoryMapByDay("all");

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

// Redirects user to the dashboard page with the current itinerary ID for editing.
function editCurrentPlanInDashboard() {
    if (currentItineraryId) {
        window.location.href = `/dashboard?itinerary_id=${currentItineraryId}`;
    } else {
        console.error("No itinerary is currently selected.");
    }
}

/**
 * Adds the day filter dropdown into the Leaflet map's top-right corner
 * using Leaflet's native Control API for history view.
 */
function addHistoryMapFilterControl() {
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
            const container = document.getElementById("historyMapDayFilterContainer");

            if (!container) {
                return L.DomUtil.create("div");
            }

            container.classList.remove("hidden");

            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.disableScrollPropagation(container);

            return container;
        }
    });

    filterControlInstance = new FilterControl();
    map.addControl(filterControlInstance);
}

/**
 * Filters the map markers and polylines based on the selected day value for history view.
 */
function filterHistoryMapByDay(dayVal) {
    if (!markersGroup || !polylineGroup || !currentItineraryData) return;

    markersGroup.clearLayers();
    polylineGroup.clearLayers();
    let bounds = [];

    currentItineraryData.days.forEach(day => {
        if (dayVal === "all" || parseInt(dayVal, 10) === parseInt(day.day_number, 10)) {
            let dayLatLngs = [];

            day.activities.forEach(act => {
                const latVal = parseFloat(act.lat);
                const lonVal = parseFloat(act.lon);

                if (!isNaN(latVal) && !isNaN(lonVal) && latVal !== 0 && lonVal !== 0) {
                    const popupText = `
                        <div style="font-family:'Inter', sans-serif;">
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
        map.invalidateSize();
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }
}

// --- CUSTOM SELECT DROPDOWN LOGIC FOR HISTORY MAP FILTER ---
document.addEventListener('click', function(e) {
    const customSelect = document.querySelector('#historyMapDayFilterContainer .custom-select');
    if (!customSelect) return;

    if (customSelect.contains(e.target)) {
        customSelect.classList.toggle('active');
    } else {
        customSelect.classList.remove('active');
    }
});

document.addEventListener('click', function(e) {
    if (e.target.classList.contains('select-option') && e.target.closest('#historyMapDayFilterContainer')) {
        const option = e.target;
        const value = option.getAttribute('data-value');
        const text = option.textContent;
        
        const customSelect = option.closest('.custom-select');
        const trigger = customSelect.querySelector('.select-trigger');
        if (trigger) {
            trigger.innerHTML = `<span class="filter-icon">📅</span> ${text}`;
        }
        
        const hiddenInput = document.getElementById('historyMapDayValue');
        if (hiddenInput) {
            hiddenInput.value = value;
        }

        filterHistoryMapByDay(value);
    }
});