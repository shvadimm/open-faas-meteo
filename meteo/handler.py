import json
import os
import time
import psycopg2
from typing import Optional
import requests
from datetime import datetime


def _read_secret_or_env(secret_name: str, env_name: str) -> str:
    secret_path = f"/var/openfaas/secrets/{secret_name}"
    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return os.getenv(env_name, "").strip()


def _weather_emoji(description: str) -> str:
    """Get weather emoji based on description"""
    description = (description or "").lower()
    if "pluie" in description or "rain" in description:
        return "🌧️"
    elif "neige" in description or "snow" in description:
        return "❄️"
    elif "orage" in description or "thunder" in description:
        return "⛈️"
    elif "nuage" in description or "cloud" in description:
        return "☁️"
    elif "soleil" in description or "clear" in description:
        return "☀️"
    return "🌤️"


def _get_db_connection():
    """Connect to PostgreSQL database"""
    try:
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "openfaas_logs")
        db_user = os.getenv("DB_USER", "openfaas_user")
        db_password = os.getenv("DB_PASSWORD", "openfaas_password")
        
        print(f"DEBUG: Connecting to {db_host}:{db_port}/{db_name}")
        
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            connect_timeout=5
        )
        print("DEBUG: Database connected successfully")
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error connecting to database: {e}")
        return None


def _log_to_postgres(function_name: str, request_data: dict, response_data: dict, 
                     status: str, duration_ms: int, error_message: str = None):
    """Log function invocation to PostgreSQL"""
    conn = _get_db_connection()
    if not conn:
        print("Warning: Could not log to database")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO function_logs 
            (function_name, request_data, response_data, status, duration_ms, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            function_name,
            json.dumps(request_data),
            json.dumps(response_data),
            status,
            duration_ms,
            error_message
        ))
        conn.commit()
        cursor.close()
        print("DEBUG: Log inserted successfully")
    except psycopg2.Error as e:
        print(f"Database insert error: {e}")
    finally:
        conn.close()


def _send_discord_message(webhook_url: str, result: dict) -> Optional[str]:
    """Send weather info to Discord webhook"""
    unit_label = "C" if result.get("units") == "metric" else result.get("units")
    description = (result.get("description") or "").lower()
    weather_emoji = _weather_emoji(description)

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
    start_time = time.time()
    query = event.query or {}
    request_data = {"query": query, "timestamp": datetime.utcnow().isoformat()}
    response_data = {}
    error_message = None
    
    city = query.get("city", "Paris")
    units = query.get("units", "metric")
    lang = query.get("lang", "fr")

    api_key = _read_secret_or_env("openweather-api-key", "OPENWEATHER_API_KEY")
    if not api_key:
        error_response = {
            "error": "OPENWEATHER_API_KEY manquante",
            "hint": "Définir la variable d'environnement de la fonction.",
        }
        duration_ms = int((time.time() - start_time) * 1000)
        _log_to_postgres(
            "meteo",
            request_data,
            error_response,
            "ERROR",
            duration_ms,
            "Missing API key"
        )
        return {
            "statusCode": 500,
            "body": json.dumps(error_response)
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
        error_response = {"error": "Erreur API météo", "details": detail}
        duration_ms = int((time.time() - start_time) * 1000)
        _log_to_postgres(
            "meteo",
            request_data,
            error_response,
            "ERROR",
            duration_ms,
            f"HTTP Error {response.status_code}"
        )
        return {"statusCode": response.status_code, "body": json.dumps(error_response)}
    except requests.RequestException as exc:
        error_response = {"error": "Erreur réseau", "details": str(exc)}
        duration_ms = int((time.time() - start_time) * 1000)
        _log_to_postgres(
            "meteo",
            request_data,
            error_response,
            "ERROR",
            duration_ms,
            str(exc)
        )
        return {"statusCode": 500, "body": json.dumps(error_response)}

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

    # Log to PostgreSQL
    response_data = result
    duration_ms = int((time.time() - start_time) * 1000)
    _log_to_postgres(
        "meteo",
        request_data,
        response_data,
        "SUCCESS",
        duration_ms
    )

    # python3-http expects a dictionary returning statusCode and body
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(result, ensure_ascii=False)
    }
