from fastapi import FastAPI
from datetime import datetime
import os
import swisseph as swe
from openai import OpenAI

app = FastAPI()

# --- Swiss Ephemeris setup ---
swe.set_ephe_path(".")

# --- OpenAI client ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.get("/")
def root():
    return {"status": "server is alive"}


@app.post("/transit-analysis")
def transit_analysis(data: dict):

    # --- Natal Julian Date ---
    natal_jd = swe.julday(
        data["year"],
        data["month"],
        data["day"],
        data["hour"]
    )

    # --- Current Transit Julian Date ---
    now = datetime.utcnow()
    transit_jd = swe.julday(
        now.year,
        now.month,
        now.day,
        now.hour + now.minute / 60.0
    )

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

    aspects = []
    energy_score = 0

    for t_name, t_planet in planets.items():
        t_pos = swe.calc_ut(transit_jd, t_planet)[0][0]

        for n_name, n_planet in planets.items():
            n_pos = swe.calc_ut(natal_jd, n_planet)[0][0]

            diff = abs(t_pos - n_pos)
            if diff > 180:
                diff = 360 - diff

            aspect_type = None
            intensity = 0

            # Conjunction
            if abs(diff - 0) <= 6:
                aspect_type = "Conjunction"
                intensity = 1 - (abs(diff - 0) / 6)

            # Opposition
            elif abs(diff - 180) <= 6:
                aspect_type = "Opposition"
                intensity = 1 - (abs(diff - 180) / 6)

            # Square
            elif abs(diff - 90) <= 6:
                aspect_type = "Square"
                intensity = 1 - (abs(diff - 90) / 6)

            # Trine
            elif abs(diff - 120) <= 6:
                aspect_type = "Trine"
                intensity = 1 - (abs(diff - 120) / 6)

            if aspect_type:
                category = "Challenging" if aspect_type in ["Square", "Opposition"] else "Supportive"
                energy_score += intensity if category == "Supportive" else -intensity

                aspects.append({
                    "transit_planet": t_name,
                    "natal_planet": n_name,
                    "aspect": aspect_type,
                    "orb": round(diff, 2),
                    "intensity_percent": round(intensity * 100, 1),
                    "category": category
                })

    if not aspects:
        return {
            "energy_index": 0,
            "overall_state": "Stable",
            "strongest_aspect": None,
            "active_aspects": []
        }

    strongest = max(aspects, key=lambda x: x["intensity_percent"])

    # --- AI Interpretation ---
    prompt = f"""
    Based on this strongest transit aspect:
    Transit planet: {strongest['transit_planet']}
    Natal planet: {strongest['natal_planet']}
    Aspect: {strongest['aspect']}
    Intensity: {strongest['intensity_percent']}%

    Provide:
    - A short psychological interpretation
    - Emotional tone
    - Recommended grounding protocol
    """

    ai_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    interpretation = ai_response.choices[0].message.content

    return {
        "energy_index": round(energy_score * 10, 2),
        "overall_state": "Emotionally Active / Growth Pressure" if energy_score < 0 else "Flow State / Expansion",
        "strongest_aspect": strongest,
        "ai_interpretation": interpretation,
        "active_aspects": aspects
    }
