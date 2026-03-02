from fastapi import FastAPI
from datetime import datetime, timedelta
import os
import swisseph as swe
from openai import OpenAI

app = FastAPI()

# Swiss Ephemeris setup
swe.set_ephe_path(".")

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.get("/")
def root():
    return {"status": "server is alive"}


@app.post("/transit-analysis")
def transit_analysis(data: dict):

    # ==========================
    # 1. EXTRACT BIRTH DATA
    # ==========================
    year = data["year"]
    month = data["month"]
    day = data["day"]
    hour = data["hour"]
    minute = data["minute"]
    timezone_offset = data["timezone_offset"]
    latitude = data["latitude"]
    longitude = data["longitude"]

    # ==========================
    # 2. CONVERT LOCAL TIME → UTC
    # ==========================
    local_decimal_hour = hour + (minute / 60.0)
    utc_decimal_hour = local_decimal_hour - timezone_offset

    birth_datetime = datetime(year, month, day) + timedelta(hours=utc_decimal_hour)

    utc_year = birth_datetime.year
    utc_month = birth_datetime.month
    utc_day = birth_datetime.day
    utc_hour = birth_datetime.hour + (birth_datetime.minute / 60.0)

    # ==========================
    # 3. JULIAN DATE
    # ==========================
    natal_jd = swe.julday(
        utc_year,
        utc_month,
        utc_day,
        utc_hour
    )

    # ==========================
    # 4. CURRENT TRANSIT JD
    # ==========================
    now = datetime.utcnow()
    transit_jd = swe.julday(
        now.year,
        now.month,
        now.day,
        now.hour + now.minute / 60.0
    )

    # ==========================
    # 5. PLANETARY POSITIONS
    # ==========================
    planets = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mercury": swe.MERCURY,
        "Venus": swe.VENUS,
        "Mars": swe.MARS,
        "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN,
        "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE,
        "Pluto": swe.PLUTO
    }

    natal_positions = {}
    transit_positions = {}

    for name, code in planets.items():
        natal_positions[name] = swe.calc_ut(natal_jd, code)[0][0]
        transit_positions[name] = swe.calc_ut(transit_jd, code)[0][0]

    # ==========================
    # 6. HOUSE CALCULATION
    # ==========================
    houses, ascmc = swe.houses(natal_jd, latitude, longitude)

    # ==========================
    # 7. ASPECT DETECTION
    # ==========================
    aspects = []
    energy_score = 0

    for t_name, t_degree in transit_positions.items():
        for n_name, n_degree in natal_positions.items():

            difference = abs(t_degree - n_degree)
            if difference > 180:
                difference = 360 - difference

            aspect_type = None
            intensity = 0

            if abs(difference - 0) <= 6:
                aspect_type = "Conjunction"
                intensity = 1 - (abs(difference - 0) / 6)

            elif abs(difference - 90) <= 6:
                aspect_type = "Square"
                intensity = 1 - (abs(difference - 90) / 6)

            elif abs(difference - 120) <= 6:
                aspect_type = "Trine"
                intensity = 1 - (abs(difference - 120) / 6)

            elif abs(difference - 180) <= 6:
                aspect_type = "Opposition"
                intensity = 1 - (abs(difference - 180) / 6)

            if aspect_type:

                category = "Challenging" if aspect_type in ["Square", "Opposition"] else "Supportive"

                if category == "Supportive":
                    energy_score += intensity
                else:
                    energy_score -= intensity

                aspects.append({
                    "transit_planet": t_name,
                    "natal_planet": n_name,
                    "aspect": aspect_type,
                    "orb": round(difference, 2),
                    "intensity_percent": round(intensity * 100, 1),
                    "category": category
                })

    if not aspects:
        return {
            "message": "No major aspects detected.",
            "energy_index": 0
        }

    strongest = max(aspects, key=lambda x: x["intensity_percent"])

    # ==========================
    # 8. AI INTERPRETATION
    # ==========================
    prompt = f"""
    Natal Moon degree: {natal_positions["Moon"]}
    Strongest Transit:
    {strongest}

    Provide:
    - Psychological interpretation
    - Emotional tone
    - Grounding strategy
    - Energy conservation advice if needed
    """

    ai_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    interpretation = ai_response.choices[0].message.content

    return {
        "energy_index": round(energy_score * 10, 2),
        "strongest_aspect": strongest,
        "ai_interpretation": interpretation,
        "natal_positions": natal_positions,
        "house_cusps": houses
    }
