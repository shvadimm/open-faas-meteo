import json
import os
from typing import Optional, Dict, List

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


def _get_weather(city: str, api_key: str, units: str, lang: str) -> Dict:
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": units,
        "lang": lang,
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def _extract_weather_data(city: str, raw_data: dict) -> Dict:
    weather = (raw_data.get("weather") or [{}])[0]
    main = raw_data.get("main") or {}
    wind = raw_data.get("wind") or {}

    return {
        "city": raw_data.get("name", city),
        "country": (raw_data.get("sys") or {}).get("country"),
        "description": weather.get("description"),
        "temperature": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "wind_speed": wind.get("speed"),
    }


def _calculate_stats(weather_list: List[Dict]) -> Dict:
    if not weather_list:
        return {}

    temps = [w.get("temperature") for w in weather_list if w.get("temperature") is not None]
    humidities = [w.get("humidity") for w in weather_list if w.get("humidity") is not None]
    wind_speeds = [w.get("wind_speed") for w in weather_list if w.get("wind_speed") is not None]

    return {
        "count": len(weather_list),
        "avg_temperature": round(sum(temps) / len(temps), 1) if temps else None,
        "min_temperature": min(temps) if temps else None,
        "max_temperature": max(temps) if temps else None,
        "avg_humidity": round(sum(humidities) / len(humidities), 1) if humidities else None,
        "avg_wind_speed": round(sum(wind_speeds) / len(wind_speeds), 1) if wind_speeds else None,
        "hottest_city": max(weather_list, key=lambda x: x.get("temperature") or -999).get("city") if temps else None,
        "coldest_city": min(weather_list, key=lambda x: x.get("temperature") or 999).get("city") if temps else None,
        "most_humid_city": max(weather_list, key=lambda x: x.get("humidity") or -999).get("city") if humidities else None,
        "windiest_city": max(weather_list, key=lambda x: x.get("wind_speed") or -999).get("city") if wind_speeds else None,
    }


def _send_discord_stats(webhook_url: str, weather_list: List[Dict], stats: Dict, units: str) -> Optional[str]:
    unit_label = "°C" if units == "metric" else "°F"
    wind_unit = "m/s" if units == "metric" else "mph"

    content = "📊 **Comparaison Météo - Statistiques**\n\n"

    content += "🏙️ **Villes analysées:**\n"
    for i, w in enumerate(weather_list, 1):
        content += f"  {i}. {w['city']}, {w['country']} - {w['description'].capitalize()}\n"

    content += "\n📈 **Statistiques globales:**\n"
    if stats.get("avg_temperature") is not None:
        content += f"  🌡️ Température moyenne: {stats['avg_temperature']}{unit_label}\n"
        content += f"  🔥 Plus chaude: {stats['hottest_city']} ({stats['max_temperature']}{unit_label})\n"
        content += f"  ❄️ Plus froide: {stats['coldest_city']} ({stats['min_temperature']}{unit_label})\n"

    if stats.get("avg_humidity") is not None:
        content += f"  💧 Humidité moyenne: {stats['avg_humidity']}%\n"
        content += f"  💦 Plus humide: {stats['most_humid_city']}\n"

    if stats.get("avg_wind_speed") is not None:
        content += f"  💨 Vent moyen: {stats['avg_wind_speed']}{wind_unit}\n"
        content += f"  🌪️ Plus venteux: {stats['windiest_city']}\n"

    try:
        response = requests.post(
            webhook_url,
            json={"content": content},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return str(exc)
    return None


def handle(event, context):
    query = event.query or {}
    body = {}
    if event.body:
        try:
            body_str = event.body.decode("utf-8") if isinstance(event.body, bytes) else event.body
            body = json.loads(body_str)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass

    cities_input = body.get("cities") or query.get("cities") or "Paris,London,Berlin"
    units = body.get("units") or query.get("units") or "metric"
    lang = body.get("lang") or query.get("lang") or "fr"

    if isinstance(cities_input, str):
        cities = [c.strip() for c in cities_input.split(",")]
    else:
        cities = cities_input

    api_key = _read_secret_or_env("openweather-api-key", "OPENWEATHER_API_KEY")
    if not api_key:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "OPENWEATHER_API_KEY manquante",
                    "hint": "Définir la variable d'environnement de la fonction.",
                }
            ),
        }

    weather_data = []
    errors = []

    for city in cities:
        try:
            raw_data = _get_weather(city, api_key, units, lang)
            weather_info = _extract_weather_data(city, raw_data)
            weather_data.append(weather_info)
        except requests.HTTPError as e:
            errors.append({"city": city, "error": f"Ville non trouvée ou API erreur: {e.response.status_code}"})
        except requests.RequestException as e:
            errors.append({"city": city, "error": f"Erreur réseau: {str(e)}"})

    if not weather_data:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {"error": "Aucune donnée météo trouvée", "details": errors},
                ensure_ascii=False,
            ),
        }

    stats = _calculate_stats(weather_data)
    webhook_url = _read_secret_or_env("discord-webhook-url", "DISCORD_WEBHOOK_URL")

    if webhook_url:
        discord_error = _send_discord_stats(webhook_url, weather_data, stats, units)

    result = {
        "cities_count": len(weather_data),
        "cities": weather_data,
        "statistics": stats,
        "errors": errors if errors else None,
        "units": units,
    }

    if webhook_url:
        result["discord"] = (
            "Message envoye sur Discord" if discord_error is None else f"Erreur envoi Discord: {discord_error}"
        )

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(result, ensure_ascii=False),
    }
