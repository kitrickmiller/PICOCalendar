import network
import urequests
import time
from picographics import PicoGraphics, DISPLAY_INKY_FRAME_SPECTRA_7 as DISPLAY
import gc

# Display setup
display = PicoGraphics(display=DISPLAY)
WIDTH, HEIGHT = display.get_bounds()

# Colors
BLACK = display.create_pen(0, 0, 0)
WHITE = display.create_pen(255, 255, 255)
RED = display.create_pen(255, 0, 0)
BLUE = display.create_pen(0, 0, 255)
ORANGE = display.create_pen(255, 140, 0)
GREEN = display.create_pen(0, 180, 0)

# Layout constants
LEFT_W = 300
DIVIDER_X = LEFT_W
RIGHT_X = LEFT_W + 10
RIGHT_W = WIDTH - RIGHT_X - 10
TIME_LABEL_W = 45
GRID_X = RIGHT_X + TIME_LABEL_W
GRID_W = WIDTH - GRID_X - 10
GRID_TOP = 55
GRID_BOTTOM = HEIGHT - 10

from secrets import WIFI_SSID, WIFI_PASSWORD, SERVER_URL

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    timeout = 30
    while not wlan.isconnected() and timeout > 0:
        time.sleep(1)
        timeout -= 1
    return wlan.isconnected()

def parse_date(date_str):
    parts = date_str.split(", ")
    day_name = parts[0]
    month_day = parts[1].split(" ")
    month_str = month_day[0]
    day_num = month_day[1]
    return day_num, day_name, month_str

def truncate(text, max_chars):
    if len(text) > max_chars:
        return text[:max_chars - 3] + "..."
    return text

def draw_left_panel(events, today_str):
    display.set_pen(WHITE)
    display.rectangle(0, 0, LEFT_W, HEIGHT)

    day_num, day_name, month_str = parse_date(today_str)

    # Big day number
    display.set_pen(BLACK)
    display.set_font("bitmap8")
    display.set_thickness(6)
    display.text(day_num, 15, 5, 90, 7)

    # Day name and month
    display.set_thickness(2)
    display.text(day_name, 95, 15, LEFT_W - 100, 3)
    display.set_thickness(1)
    display.text(month_str + " 2026", 95, 55, LEFT_W - 100, 2)

    # Red divider
    display.set_pen(RED)
    display.line(15, 95, LEFT_W - 15, 95, 2)

    # Upcoming label
    display.set_pen(BLACK)
    display.set_font("bitmap8")
    display.set_thickness(1)
    display.text("Upcoming", 15, 103, LEFT_W - 20, 2)

    # Events list
    y = 125
    text_width = LEFT_W - 30
    EVENT_HEIGHT = 44

    for event in events:
        if event.get("is_today"):
            continue

        if y + EVENT_HEIGHT > HEIGHT - 5:
            break

        date_text = f"{event['date']}  {event['time']}"
        display.set_pen(BLUE)
        display.set_thickness(1)
        display.text(truncate(date_text, 28), 15, y, text_width, 2)
        y += 18

        display.set_pen(BLACK)
        display.set_thickness(2)
        display.text(truncate(event['title'], 28), 15, y, text_width, 2)
        y += 26

def draw_right_panel(today_events):
    # Header
    display.set_pen(BLACK)
    display.set_font("bitmap8")
    display.set_thickness(2)
    display.text("Today", RIGHT_X, 10, RIGHT_W, 3)

    # Red divider
    display.set_pen(RED)
    display.line(RIGHT_X, 40, WIDTH - 10, 40, 2)

    # Fixed time range 8AM - 7PM
    min_hour = 8
    max_hour = 19
    total_hours = max_hour - min_hour
    pixels_per_hour = (GRID_BOTTOM - GRID_TOP) / total_hours

    # Draw hour lines and labels
    for h in range(min_hour, max_hour + 1):
        y = int(GRID_TOP + (h - min_hour) * pixels_per_hour)
        if y > GRID_BOTTOM:
            break

        display.set_pen(BLACK)
        display.set_font("bitmap8")
        display.set_thickness(1)
        if h < 12:
            label = f"{h}AM"
        elif h == 12:
            label = "12PM"
        else:
            label = f"{h-12}PM"
        display.text(label, RIGHT_X, y - 6, TIME_LABEL_W, 2)

        display.set_pen(BLACK)
        display.line(GRID_X, y, WIDTH - 10, y, 1)

    # Draw all-day events as a bar at top
    all_day = [e for e in today_events if e.get("all_day")]
    ay = GRID_TOP - 12
    for event in all_day:
        display.set_pen(GREEN)
        display.rectangle(GRID_X, ay - 10, GRID_W, 14)
        display.set_pen(WHITE)
        display.set_thickness(1)
        display.text(truncate(event['title'], 30), GRID_X + 3, ay - 9, GRID_W - 6, 2)
        ay += 16

    # Draw timed event blocks with overlap detection
    timed = [e for e in today_events if not e.get("all_day") and e.get("start_hour") is not None]
    colors = [BLUE, ORANGE, GREEN, RED]

    def get_y(hour, minute):
        frac = (hour - min_hour) + minute / 60
        return int(GRID_TOP + frac * pixels_per_hour)

    # Assign columns to events to handle overlaps
    columns = []
    for i, event in enumerate(timed):
        start_y = get_y(event["start_hour"], event["start_minute"])
        end_h = event["end_hour"] if event["end_hour"] is not None else event["start_hour"] + 1
        end_m = event["end_minute"] if event["end_minute"] is not None else 0
        end_y = get_y(end_h, end_m)
        if end_y - start_y < 25:
            end_y = start_y + 25

        overlapping_cols = []
        for j, other in enumerate(timed):
            if j >= i:
                break
            other_start_y = get_y(other["start_hour"], other["start_minute"])
            other_end_h = other["end_hour"] if other["end_hour"] is not None else other["start_hour"] + 1
            other_end_m = other["end_minute"] if other["end_minute"] is not None else 0
            other_end_y = get_y(other_end_h, other_end_m)
            if other_end_y - other_start_y < 25:
                other_end_y = other_start_y + 25
            if start_y < other_end_y and end_y > other_start_y:
                overlapping_cols.append(columns[j][0])

        col = 0
        while col in overlapping_cols:
            col += 1
        columns.append((col, 0))

    # Calculate total columns needed per event group
    for i in range(len(timed)):
        start_y = get_y(timed[i]["start_hour"], timed[i]["start_minute"])
        end_h = timed[i]["end_hour"] if timed[i]["end_hour"] is not None else timed[i]["start_hour"] + 1
        end_m = timed[i]["end_minute"] if timed[i]["end_minute"] is not None else 0
        end_y = get_y(end_h, end_m)
        if end_y - start_y < 25:
            end_y = start_y + 25

        max_col = columns[i][0]
        for j in range(len(timed)):
            if i == j:
                continue
            other_start_y = get_y(timed[j]["start_hour"], timed[j]["start_minute"])
            other_end_h = timed[j]["end_hour"] if timed[j]["end_hour"] is not None else timed[j]["start_hour"] + 1
            other_end_m = timed[j]["end_minute"] if timed[j]["end_minute"] is not None else 0
            other_end_y = get_y(other_end_h, other_end_m)
            if other_end_y - other_start_y < 25:
                other_end_y = other_start_y + 25
            if start_y < other_end_y and end_y > other_start_y:
                if columns[j][0] > max_col:
                    max_col = columns[j][0]

        columns[i] = (columns[i][0], max_col + 1)

    # Draw events
    for i, event in enumerate(timed):
        col_index, total_cols = columns[i]
        col_width = GRID_W // total_cols
        x_start = GRID_X + col_index * col_width

        start_h = event["start_hour"]
        start_m = event["start_minute"]
        end_h = event["end_hour"] if event["end_hour"] is not None else start_h + 1
        end_m = event["end_minute"] if event["end_minute"] is not None else 0

        y_start = get_y(start_h, start_m)
        y_end = get_y(end_h, end_m)

        if y_end - y_start < 25:
            y_end = y_start + 25

        y_start = max(GRID_TOP, min(y_start, GRID_BOTTOM))
        y_end = max(GRID_TOP, min(y_end, GRID_BOTTOM))

        display.set_pen(colors[i % len(colors)])
        display.rectangle(x_start, y_start, col_width - 2, y_end - y_start)

        # Draw multi-line text to fill the block
        display.set_pen(WHITE)
        display.set_thickness(2)

        block_height = y_end - y_start
        line_height = 18
        max_lines = max(1, block_height // line_height)
        max_chars = 15 if total_cols > 1 else 30

        words = event['title'].split(" ")
        lines = []
        current_line = ""
        for word in words:
            test = current_line + " " + word if current_line else word
            if len(test) <= max_chars:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
            if len(lines) >= max_lines:
                break
        if current_line and len(lines) < max_lines:
            lines.append(current_line)

        for li, line in enumerate(lines):
            ty = y_start + 4 + li * line_height
            if ty + line_height > y_end:
                break
            display.text(line, x_start + 3, ty, col_width - 6, 2)

    if not timed and not all_day:
        display.set_pen(BLACK)
        display.set_thickness(1)
        display.text("No events today", GRID_X, GRID_TOP + 20, GRID_W, 2)

def draw_dashboard(events, today_str):
    display.set_pen(WHITE)
    display.clear()

    today_events = [e for e in events if e.get("is_today")]

    draw_left_panel(events, today_str)

    display.set_pen(BLACK)
    display.line(DIVIDER_X, 0, DIVIDER_X, HEIGHT, 1)

    draw_right_panel(today_events)

    display.update()

# Main loop
while True:
    print("Connecting to WiFi...")

    if connect_wifi():
        print("Connected!")
        time.sleep(3)
        try:
            gc.collect()
            response = urequests.get(SERVER_URL, timeout=15)
            data = response.json()
            response.close()
            events = data.get("events", [])
            print(f"Got {len(events)} events")

            today_events = [e for e in events if e.get("is_today")]
            if today_events:
                today_str = today_events[0]["date"]
            else:
                today_str = events[0]["date"] if events else "Sunday, Jan 01"

            draw_dashboard(events, today_str)
            print("Dashboard drawn!")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("WiFi failed!")

    network.WLAN(network.STA_IF).active(False)
    print("Sleeping 1 hour...")
    time.sleep(60 * 60)
