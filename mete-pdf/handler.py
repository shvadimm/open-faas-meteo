import json
import os
from typing import Optional, Dict, List

import requests
from fpdf import FPDF


def _read_secret_or_env(secret_name: str, env_name: str) -> str:
    secret_path = f"/var/openfaas/secrets/{secret_name}"
    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return os.getenv(env_name, "").strip()


def _get_coordinates(city: str, api_key: str) -> Dict[str, object]:
    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {"q": city, "limit": 1, "appid": api_key}

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"Ville introuvable: {city}")

    location = data[0]
    return {
        "lat": location.get("lat"),
        "lon": location.get("lon"),
        "country": location.get("country", ""),
    }


def _get_weekly_forecast(lat: float, lon: float, api_key: str, units: str, lang: str) -> dict:
    url = "https://api.openweathermap.org/data/2.5/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "exclude": "current,minutely,hourly,alerts",
        "appid": api_key,
        "units": units,
        "lang": lang,
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def _weekday_name(timestamp: int, tz_offset: int, lang: str) -> str:
    utc = __import__("datetime").datetime.utcfromtimestamp(timestamp + tz_offset)
    weekday = utc.weekday()

    if str(lang).lower().startswith("fr"):
        days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    else:
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    return f"{days[weekday]} {utc.strftime('%d/%m')}"


def _format_number(value: Optional[float], precision: int = 1) -> str:
    if value is None:
        return "?"
    try:
        return f"{value:.{precision}f}"
    except (TypeError, ValueError):
        return str(value)


def _build_pdf_report(city: str, country: str, raw_data: dict, units: str, lang: str) -> bytes:
    tz_offset = raw_data.get("timezone_offset", 0)
    daily = raw_data.get("daily", [])[:7]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(0, 10, "Rapport meteo hebdomadaire", ln=True, align="C")
    pdf.ln(6)

    pdf.set_font("Arial", size=12)
    summary = f"Rapport meteo hebdomadaire pour {city}, {country}."
    pdf.multi_cell(0, 8, summary)
    pdf.ln(4)

    for day in daily:
        weather = (day.get("weather") or [{}])[0]
        description = weather.get("description", "").capitalize()
        date_label = _weekday_name(day.get("dt", 0), tz_offset, lang)
        temp_min = _format_number(day.get("temp", {}).get("min"))
        temp_max = _format_number(day.get("temp", {}).get("max"))
        humidity = int(day.get("humidity", 0)) if isinstance(day.get("humidity"), (int, float)) else "?"
        wind_speed = _format_number(day.get("wind_speed"))
        pop = int(day.get("pop", 0) * 100) if isinstance(day.get("pop", 0), (int, float)) else "?"

        line = (
            f"{date_label} - {description} - "
            f"{temp_min}/{temp_max}°{'C' if units == 'metric' else 'F'} - "
            f"Hum {humidity}% - Vent {wind_speed} m/s - Pluie {pop}%"
        )
        pdf.multi_cell(0, 8, line)
        pdf.ln(1)

    raw = pdf.output(dest="S")
    if isinstance(raw, str):
        return raw.encode("latin-1", "replace")
    return raw


def _send_discord_file(webhook_url: str, pdf_bytes: bytes, filename: str = "mete-hebdo.pdf", message: str = "Rapport meteo hebdomadaire") -> Optional[str]:
    try:
        response = requests.post(
            webhook_url,
            data={"content": message},
            files={"file": (filename, pdf_bytes, "application/pdf")},
            timeout=20,
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

    city = body.get("city") or query.get("city") or "Paris"
    units = body.get("units") or query.get("units") or "metric"
    lang = body.get("lang") or query.get("lang") or "fr"

    api_key = _read_secret_or_env("openweather-api-key", "OPENWEATHER_API_KEY")
    if not api_key:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json; charset=utf-8"},
            "body": json.dumps({"error": "OPENWEATHER_API_KEY manquante"}, ensure_ascii=False),
        }

    webhook_url = _read_secret_or_env("discord-webhook-url", "DISCORD_WEBHOOK_URL")

    try:
        location = _get_coordinates(city, api_key)
        forecast_data = _get_weekly_forecast(
            lat=location["lat"],
            lon=location["lon"],
            api_key=api_key,
            units=units,
            lang=lang,
        )
        pdf_bytes = _build_pdf_report(city, location.get("country", ""), forecast_data, units, lang)

        discord_header = None
        if webhook_url:
            discord_error = _send_discord_file(webhook_url, pdf_bytes)
            discord_header = "Discord-PDF-Sent" if discord_error is None else f"Discord-Error: {discord_error}"

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename=mete-hebdo.pdf",
                **({"X-Discord-Status": discord_header} if discord_header else {}),
            },
            "body": pdf_bytes,
        }
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return {
            "statusCode": exc.response.status_code if exc.response is not None else 500,
            "headers": {"Content-Type": "application/json; charset=utf-8"},
            "body": json.dumps({"error": "Erreur API météo", "details": detail}, ensure_ascii=False),
        }
    except Exception as exc:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json; charset=utf-8"},
            "body": json.dumps({"error": "Erreur interne", "details": str(exc)}, ensure_ascii=False),
        }