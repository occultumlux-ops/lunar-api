from fastapi import FastAPI
from datetime import datetime
import pyswisseph as swe
from openai import OpenAI
import os

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

    natal_jd = swe.julday(
        data["year"],
        data["month"],
        data["day"],
        data["hour"]
    )

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

    natal_positions = {}
    transit_positions = {}

    for name, code in planets.items():
        natal_positions[name] = swe.calc_ut(natal_jd, code)[0][0]
        transit_positions[name] = swe.calc_ut(transit_jd, code)[0][0]

    aspects = []
    total_supportive = 0
    total_challenging = 0

    for t_name, t_degree in transit_positions.items():
        for n_name, n_degree in natal_positions.items():

            difference = abs(t_degree - n_degree) % 360
            if difference > 180:
                difference = 360 - difference

            aspect_type = None
            orb = None

            if difference < 8:
                aspect_type = "Conjunction"
                orb = difference
            elif abs(difference - 90) < 8:
                aspect_type = "Square"
                orb = abs(difference - 90)
            elif abs(difference - 120) < 8:
                aspect_type = "Trine"
                orb = abs(difference - 120)
            elif abs(difference - 180) < 8:
                aspect_type = "Opposition"
                orb = abs(difference - 180)

            if aspect_type:

                intensity = round((8 - orb) / 8 * 100, 1)

                if aspect_type == "Trine":
                    category = "Supportive"
                    total_supportive += intensity
                elif aspect_type in ["Square", "Opposition"]:
                    category = "Challenging"
                    total_challenging += intensity
                else:
                    category = "Neutral"

                if intensity >= 80 and category == "Challenging":
                    protocol = "Grounding + Breathwork + Slow Decisions"
                elif intensity >= 70 and category == "Supportive":
                    protocol = "Take Action + Create + Strategic Moves"
                elif category == "Challenging":
                    protocol = "Reflect + Journal + Emotional Awareness"
                else:
                    protocol = "Maintain Flow State"

                aspects.append({
                    "transit_planet": t_name,
                    "natal_planet": n_name,
                    "aspect": aspect_type,
                    "orb": round(orb, 2),
                    "intensity_percent": intensity,
                    "category": category,
                    "recommended_protocol": protocol
                })

    energy_index = round(total_supportive - total_challenging, 1)

    if energy_index > 100:
        overall_state = "High Momentum Day"
    elif energy_index > 0:
        overall_state = "Mildly Supportive"
    elif energy_index == 0:
        overall_state = "Neutral Field"
    elif energy_index > -100:
        overall_state = "Emotionally Active / Growth Pressure"
    else:
        overall_state = "High Friction Day – Slow Down"

    strongest_aspect = max(aspects, key=lambda x: x["intensity_percent"]) if aspects else None

    # -----------------------------
    # AI INTERPRETATION LAYER
    # -----------------------------

    summary_prompt = f"""
    Energy Index: {energy_index}
    Overall State: {overall_state}
    Strongest Aspect: {strongest_aspect}

    Provide a psychologically intelligent daily transit interpretation.
    Focus on emotional tone, nervous system regulation, decision-making strategy,
    and grounded personal power. Avoid mystical language.
    """

    ai_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a psychologically intelligent astrology interpreter."},
            {"role": "user", "content": summary_prompt}
        ],
        temperature=0.7
    )

    interpretation = ai_response.choices[0].message.content

    return {
        "energy_index": energy_index,
        "overall_state": overall_state,
        "strongest_aspect": strongest_aspect,
        "active_aspects": aspects,
        "ai_interpretation": interpretation
    }
