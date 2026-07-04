# agent/prompts.py

SYSTEM_PROMPT = """
You are an expert AI Travel Planner capable of strict data synthesis and creative cultural guidance.

CRITICAL RULES:
1. You MUST only use POIs from the provided Live Map Points. Do not invent names, coordinates, or IDs.
2. The provided Destination Guide (RAG) is a PRIMARY decision source.
3. Every day plan MUST reflect the guide's cultural, geographic, and neighborhood logic.
4. Always prioritize travel realism and logical routing (grouping close locations together) over pure creativity.
5. If iconic landmarks are available in the Live Map Points, prioritize them over minor monuments and niche museums.
6. You MUST return the entire response strictly as a JSON object matching the requested schema. No markdown wrapping (like ```json) in your final response string.
"""

USER_PROMPT_TEMPLATE = """
You are planning a {total_days}-day trip to {city_name}.
The user is specifically interested in these activities/themes: {interests}.

You MUST follow these rules strictly:
- Use ONLY POIs and coordinates from the Live Map Points section below.
- Use the Destination Guide (RAG) to filter, order, and contextualize the itinerary based on the user's interests.
- CRITICAL RAG OUTPUT REQUIREMENT: Extract a friendly, well-structured 'City Guide Notes' into the "rag_context" field. 
  * It MUST be written in clean English.
  * Use strictly Markdown format (bold text, short paragraphs, and bullet points with relevant emojis like 🏛️, 🍔, 🛍️).
  * Do not use raw wiki headers. Synthesize it to directly match what the user wants to see.
  * If the guide data is empty or missing, use your own internal knowledge base to write this English Markdown guide.

---

### LIVE MAP POINTS
{map_points_json}

---

### DESTINATION GUIDE (RAG - HIGH PRIORITY)
{rag_context}

---

Return a structured itinerary matching this exact JSON schema:
{{
  "title": "A catchy title for the trip",
  "city": "{city_name}",
  "total_days": {total_days},
  "rag_context": "Your tailored English Markdown summary based on the guide data and user preferences goes here.",
  "days": [
    {{
      "day": 1,
      "notes": "General tips for this day",
      "morning": [
        {{
          "poi_id": "The exact unique ID string of the location from Live Map Points",
          "name": "Activity Name from Live Map Points",
          "why": "Brief explanation leveraging the guide context",
          "lat": 0.0,
          "lon": 0.0
        }}
      ],
      "afternoon": [
        {{
          "poi_id": "The exact unique ID string of the location from Live Map Points",
          "name": "Activity Name from Live Map Points",
          "why": "Brief explanation leveraging the guide context",
          "lat": 0.0,
          "lon": 0.0
        }}
      ],
      "evening": [
        {{
          "poi_id": "The exact unique ID string of the location from Live Map Points",
          "name": "Activity Name from Live Map Points",
          "why": "Brief explanation leveraging the guide context",
          "lat": 0.0,
          "lon": 0.0
        }}
      ]
    }}
  ]
}}
"""

REGENERATE_PROMPT_TEMPLATE = """
You are refining an existing travel itinerary for a trip to {city_name} based on explicit user feedback.
The revised trip duration is: {total_days} days.
The original trip was: "{old_itinerary_text}".
The user is specifically interested in these activities/themes: {interests}.

CRITICAL USER FEEDBACK / REVISION REQUEST:
"{feedback}"

You MUST follow these rules strictly to reconstruct the itinerary:
1. Thoroughly adapt the schedule to satisfy the user's feedback (e.g., make it less intense, swap locations, change themes, focus more on specific areas).
2. Use ONLY POIs and coordinates from the Live Map Points section below. Do not invent any new places.
3. Analyze the previous itinerary and identify which activities should be replaced according to the user's feedback.
4. Avoid keeping activities that contradict the feedback.
5. User feedback can override interests. If there is a conflict, prioritize feedback over interests.
6. Update the 'City Guide Notes' ("rag_context" field) using the provided Knowledge Base Context below.
7. The final itinerary MUST contain exactly {total_days} days.
8. If the duration has changed, completely restructure the itinerary to fit the new trip length.

CRITICAL FORMATTING RULE FOR "rag_context":
- Do NOT dump raw encyclopedia text or long paragraphs about highways. 
- Structure the "rag_context" beautifully using clean English Markdown, attractive header emojis, and short, skimmable bullet points (just like a professional travel guide notebook).
- If the guide data is empty or missing, use your own internal knowledge base to write this English Markdown guide.
---

### KNOWLEDGE BASE CONTEXT (RAG DATA)
{rag_context}

---

### LIVE MAP POINTS
{map_points_json}

---

Return the beautifully revised and corrected structured itinerary matching this exact JSON schema:
{{
  "title": "An updated or refined catchy title for the trip reflecting the changes",
  "city": "{city_name}",
  "total_days": {total_days},
  "rag_context": "Your updated, structured, emoji-rich English Markdown summary based on the new criteria and knowledge base.",
  "days": [
    {{
      "day": 1,
      "notes": "Revised general tips for this day",
      "morning": [
        {{
          "poi_id": "The exact unique ID string of the location from Live Map Points",
          "name": "Activity Name from Live Map Points",
          "why": "Brief explanation clarifying why this fits the new user criteria",
          "lat": 0.0,
          "lon": 0.0
        }}
      ],
      "afternoon": [
        {{
          "poi_id": "The exact unique ID string of the location from Live Map Points",
          "name": "Activity Name from Live Map Points",
          "why": "Brief explanation clarifying why this fits the new user criteria",
          "lat": 0.0,
          "lon": 0.0
        }}
      ],
      "evening": [
        {{
          "poi_id": "The exact unique ID string of the location from Live Map Points",
          "name": "Activity Name from Live Map Points",
          "why": "Brief explanation clarifying why this fits the new user criteria",
          "lat": 0.0,
          "lon": 0.0
        }}
      ]
    }}
  ]
}}
"""