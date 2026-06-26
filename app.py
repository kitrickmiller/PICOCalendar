from flask import Flask, jsonify
import requests
import recurring_ical_events
from icalendar import Calendar
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

app = Flask(__name__)

# --- SETTINGS ---
ICAL_URLS = [
    "https://your-first-ical-url.ics",
    "https://your-second-ical-url.ics",
]
TIMEZONE = ZoneInfo("America/Los_Angeles")  # change to your timezone
# ----------------

@app.route("/events")
def get_events():
    try:
        now = datetime.now(tz=TIMEZONE)
        month_ahead = now + timedelta(days=30)
        events = []

        for ical_url in ICAL_URLS:
            response = requests.get(ical_url)
            cal = Calendar.from_ical(response.text)
            occurrences = recurring_ical_events.of(cal).between(now, month_ahead)

            for component in occurrences:
                summary = str(component.get("SUMMARY", "No Title"))
                description = str(component.get("DESCRIPTION", ""))
                dtstart = component.get("DTSTART").dt

                if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
                    dtstart = datetime(dtstart.year, dtstart.month, dtstart.day, tzinfo=TIMEZONE)
                    all_day = True
                else:
                    if dtstart.tzinfo is None:
                        dtstart = dtstart.replace(tzinfo=TIMEZONE)
                    else:
                        dtstart = dtstart.astimezone(TIMEZONE)
                    all_day = False

                dtend = component.get("DTEND")
                end_hour = None
                end_minute = None
                if dtend:
                    dtend = dtend.dt
                    if isinstance(dtend, date) and not isinstance(dtend, datetime):
                        dtend = datetime(dtend.year, dtend.month, dtend.day, tzinfo=TIMEZONE)
                    elif isinstance(dtend, datetime) and dtend.tzinfo is None:
                        dtend = dtend.replace(tzinfo=TIMEZONE)
                    elif isinstance(dtend, datetime):
                        dtend = dtend.astimezone(TIMEZONE)
                    if not all_day:
                        end_hour = dtend.hour
                        end_minute = dtend.minute

                events.append({
                    "title": summary,
                    "description": description[:100] if description else "",
                    "date": dtstart.strftime("%A, %b %d"),
                    "time": dtstart.strftime("%I:%M %p"),
                    "timestamp": dtstart.isoformat(),
                    "start_hour": dtstart.hour,
                    "start_minute": dtstart.minute,
                    "end_hour": end_hour,
                    "end_minute": end_minute,
                    "all_day": all_day,
                    "is_today": dtstart.date() == now.date()
                })

        events.sort(key=lambda x: x["timestamp"])
        return jsonify({"events": events})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run()
