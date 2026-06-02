import json
import os
from urllib.parse import parse_qs

import requests


def _read_api_key() -> str:
    secret_path = "/var/openfaas/secrets/openweather-api-key"
    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return os.getenv("OPENWEATHER_API_KEY", "").strip()


def handle(req: str) -> str:
    query = parse_qs(req or "")
    city = query.get("city", ["Paris"])[0]
    units = query.get("units", ["metric"])[0]
    lang = query.get("lang", ["fr"])[0]

    api_key = _read_api_key()
    if not api_key:
        return json.dumps(
            {
                "error": "OPENWEATHER_API_KEY manquante",
                "hint": "Définir la variable d'environnement de la fonction.",
            }
        )

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
        return json.dumps({"error": "Erreur API météo", "details": detail})
    except requests.RequestException as exc:
        return json.dumps({"error": "Erreur réseau", "details": str(exc)})

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
    return json.dumps(result, ensure_ascii=False)
