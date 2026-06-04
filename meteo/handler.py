import json
import os
import datetime
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


def _unit_label(units: str) -> str:
    if units == "metric":
        return "C"
    if units == "imperial":
        return "F"
    return units or ""


def _weather_emoji(description: str) -> str:
    desc = (description or "").lower()
    if "pluie" in desc or "rain" in desc:
        return "🌧️"
    if "neige" in desc or "snow" in desc:
        return "❄️"
    if "orage" in desc or "thunder" in desc:
        return "⛈️"
    if "nuage" in desc or "cloud" in desc:
        return "☁️"
    if "soleil" in desc or "clear" in desc:
        return "☀️"
    return "🌤️"


def _weekday_name(timestamp: int, tz_offset: int, lang: str) -> str:
    utc = datetime.datetime.utcfromtimestamp(timestamp + tz_offset)
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


def _format_weekly_report(city: str, country: str, raw_data: dict, units: str, lang: str) -> dict:
    tz_offset = raw_data.get("timezone_offset", 0)
    daily = raw_data.get("daily", [])[:7]

    report_days = []
    for day in daily:
        weather = (day.get("weather") or [{}])[0]
        description = weather.get("description", "")
        report_days.append(
            {
                "date": _weekday_name(day.get("dt", 0), tz_offset, lang),
                "description": description.capitalize(),
                "emoji": _weather_emoji(description),
                "temp_min": _format_number(day.get("temp", {}).get("min")),
                "temp_max": _format_number(day.get("temp", {}).get("max")),
                "humidity": int(day.get("humidity", 0)) if isinstance(day.get("humidity"), (int, float)) else "?",
                "wind_speed": _format_number(day.get("wind_speed")),
                "pop": int(day.get("pop", 0) * 100) if isinstance(day.get("pop", 0), (int, float)) else "?",
            }
        )

    summary = f"Rapport meteo hebdomadaire pour {city}, {country}."
    lines = []
    for day in report_days:
        lines.append(
            f"{day['date']} - {day['emoji']} {day['description']} - "
            f"{day['temp_min']}/{day['temp_max']}°{_unit_label(units)} - "
            f"Hum {day['humidity']}% - Vent {day['wind_speed']} m/s - Pluie {day['pop']}%"
        )

    return {
        "summary": summary,
        "lines": lines,
        "days": report_days,
    }


def _build_pdf_report(city: str, country: str, summary_text: str, report_lines: List[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(0, 10, "Rapport meteo hebdomadaire", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 8, summary_text)
    pdf.ln(4)

    for line in report_lines:
        pdf.multi_cell(0, 8, line)

    raw = pdf.output(dest="S")
    if isinstance(raw, str):
        return raw.encode("latin-1", "replace")
    return raw


def _send_discord_report(webhook_url: str, report_text: str, pdf_bytes: bytes, filename: str = "rapport_meteo_semaine.pdf") -> Optional[str]:
    try:
        response = requests.post(
            webhook_url,
            data={"content": report_text},
            files={"file": (filename, pdf_bytes, "application/pdf")},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return str(exc)
    return None


def _send_discord_message(webhook_url: str, result: dict) -> Optional[str]:
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
    mode = body.get("mode") or query.get("mode") or "current"

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

    webhook_url = _read_secret_or_env("discord-webhook-url", "DISCORD_WEBHOOK_URL")

    if str(mode).lower() in {"weekly", "weekly_report", "report_weekly"}:
        try:
            location = _get_coordinates(city, api_key)
            forecast_data = _get_weekly_forecast(
                lat=location["lat"],
                lon=location["lon"],
                api_key=api_key,
                units=units,
                lang=lang,
            )
            report = _format_weekly_report(city, location.get("country", ""), forecast_data, units, lang)
            pdf_bytes = _build_pdf_report(city, location.get("country", ""), report["summary"], report["lines"])

            result = {
                "city": city,
                "country": location.get("country"),
                "units": units,
                "mode": "weekly",
                "summary": report["summary"],
                "forecast": report["days"],
            }

            if webhook_url:
                discord_error = _send_discord_report(webhook_url, report["summary"], pdf_bytes)
                result["discord"] = (
                    "PDF envoye sur Discord" if discord_error is None else f"Erreur envoi Discord: {discord_error}"
                )

            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json; charset=utf-8"},
                "body": json.dumps(result, ensure_ascii=False),
            }
        except requests.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.json()
            except Exception:
                detail = exc.response.text if exc.response is not None else str(exc)
            return {"statusCode": exc.response.status_code if exc.response is not None else 500, "body": json.dumps({"error": "Erreur API meteo", "details": detail})}
        except ValueError as exc:
            return {"statusCode": 404, "body": json.dumps({"error": str(exc)})}
        except requests.RequestException as exc:
            return {"statusCode": 500, "body": json.dumps({"error": "Erreur reseau", "details": str(exc)})}

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
        return {"statusCode": response.status_code, "body": json.dumps({"error": "Erreur API meteo", "details": detail})}
    except requests.RequestException as exc:
        return {"statusCode": 500, "body": json.dumps({"error": "Erreur reseau", "details": str(exc)})}

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

    if webhook_url:
        discord_error = _send_discord_message(webhook_url, result)
        if discord_error:
            result["discord"] = f"Erreur envoi webhook: {discord_error}"
        else:
            result["discord"] = "Message envoye"

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(result, ensure_ascii=False),
    }
