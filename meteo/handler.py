import json
import os
from typing import Optional
import requests

def _read_secret_or_env(secret_name: str, env_name: str) -> str:
    secret_path = f"/var/openfaas/secrets/{secret_name}"
    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return os.getenv(env_name, "").strip()


def _send_discord_message(webhook_url: str, result: dict) -> Optional[str]:
    unit_label = "C" if result.get("units") == "metric" else result.get("units")
    description = (result.get("description") or "").lower()
    weather_emoji = "🌤️"
    
    if "pluie" in description or "rain" in description:
        weather_emoji = "🌧️"
    elif "neige" in description or "snow" in description:
        weather_emoji = "❄️"
    elif "orage" in description or "thunder" in description:
        weather_emoji = "⛈️"
    elif "nuage" in description or "cloud" in description:
        weather_emoji = "☁️"
    elif "soleil" in description or "clear" in description:
        weather_emoji = "☀️"

    content = (
        f"📍 **Meteo pour {result.get('city')}, {result.get('country')}**\n"
        f"{weather_emoji} **Conditions**: {result.get('description')}\n"
        f"🌡️ **Temperature**: {result.get('temperature')}°{unit_label}\n"
        f"🤗 **Ressenti**: {result.get('feels_like')}°{unit_label}\n"
        f"💧 **Humidite**: {result.get('humidity')}%\n"
        f"💨 **Vent**: {result.get('wind_speed')} m/s"
    )
    
    try:
        webhook_response = requests.post(
            webhook_url,
            json={"content": content},
            timeout=10,
        )
        webhook_response.raise_for_status()
    except requests.RequestException as exc:
        return str(exc)
    return None



def handle(event, context):
if 
    query = event.query or {}
 body = {}
    if event.body:
        try:

            body_str = event.body.decode('utf-8') if isinstance(event.body, bytes) else event.body
            body = json.loads(body_str)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass 

    city = body.get("city") or query.get("city") or "Paris"
    units = body.get("units") or query.get("units") or "metric"
    lang = body.get("lang") or query.get("lang") or "fr"
    
    api_key = _read_secret_or_env("openweather-api-key", "OPENWEATHER_API_KEY")
    
    if not api_key:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "OPENWEATHER_API_KEY manquante",
                    "hint": "Définir la variable d'environnement de la fonction.",
                }
            )
        }

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": units,
        "lang": lang,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.HTTPError:
        detail = ""
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        return {"statusCode": response.status_code, "body": json.dumps({"error": "Erreur API météo", "details": detail})}
    except requests.RequestException as exc:
        return {"statusCode": 500, "body": json.dumps({"error": "Erreur réseau", "details": str(exc)})}

    data = response.json()
    weather = (data.get("weather") or [{}])[0]
    main = data.get("main") or {}
    wind = data.get("wind") or {}
    sys_data = data.get("sys") or {}

    result = {
        "city": data.get("name", city),
        "country": sys_data.get("country"),
        "description": weather.get("description"),
        "temperature": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "wind_speed": wind.get("speed"),
        "units": units,
    }

    webhook_url = _read_secret_or_env("discord-webhook-url", "DISCORD_WEBHOOK_URL")
    if webhook_url:
        discord_error = _send_discord_message(webhook_url, result)
        if discord_error:
            result["discord"] = f"Erreur envoi webhook: {discord_error}"
        else:
            result["discord"] = "Message envoye"

    # python3-http expects a dictionary returning statusCode and body
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(result, ensure_ascii=False)
    }