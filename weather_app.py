import datetime as dt
import json
import requests
from flask import Flask, jsonify, request
import os
from google import genai

API_TOKEN = os.environ.get("API_TOKEN")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)
app = Flask(__name__)


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self):
        return {"message": self.message}


def fetch_weather_data(location, date, unit_group="metric"):

    base_url = ("https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline")

    elements = ",".join([
        "datetime","temp","feelslike","humidity","windspeed","pressure","uvindex","conditions"
    ])

    request_url = (
        f"{base_url}/{location}/{date}"
        f"?unitGroup={unit_group}"
        f"&key={WEATHER_API_KEY}"
        f"&include=days"
        f"&elements={elements}"
        f"&lang=en"
    )

    response = requests.get(request_url)

    if response.status_code == requests.codes.ok:

        data = json.loads(response.text)
        return data

    else:

        raise InvalidUsage(
            response.text,
            status_code=response.status_code
        )


def get_ai_recommendation(day_data):
    prompt = f"""
    Weather Data:
    - Temp: {day_data.get('temp')}°C
    - Wind: {day_data.get('windspeed')} kph
    - Humidity: {day_data.get('humidity')}%
    - Conditions: {day_data.get('conditions')}

    Provide clothing advice fast in only one sentence
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"GenAI Error: {e}")
        return "AI recommendation service is currently unavailable."
        
@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route("/")
def home_page():
    return "<h2>Weather SaaS API</h2>"


@app.route("/content/api/v1/weather", methods=["POST"])
def weather_endpoint():
    start_dt = dt.datetime.utcnow()
    json_data = request.get_json()

    if not json_data.get("token"):
        raise InvalidUsage("token is required")

    if json_data["token"] != API_TOKEN:
        raise InvalidUsage("wrong API token", status_code=403)

    requester_name = json_data.get("requester_name")
    location = json_data.get("location")
    date = json_data.get("date")

    if not requester_name or not location or not date:
        raise InvalidUsage("requester_name, location and date are required")

    weather_data = fetch_weather_data(location, date)

    day = (weather_data.get('days'))[0]
    ai_recommendation = get_ai_recommendation(day)
    
    response = {
        "requester_name": requester_name,
        "timestamp": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": location,
        "date": date,
        "weather": day,
        "ai_recommendation": ai_recommendation
    }

    return jsonify(response)

