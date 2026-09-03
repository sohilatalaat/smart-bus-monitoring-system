# ============================================================
# STATION CORE - Two OLED screens
# Screen 1 (0x3C) : arrival board -> ARRIVED / leaving in / next bus
# Screen 2 (0x3D) : bus occupancy details
# ============================================================

import network
import time
import ujson
import urandom
from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
from umqtt_simple import MQTTClient


# =========================================================
# CONFIGURATION  <-- ONLY THIS NUMBER CHANGES PER STATION
# =========================================================

STATION_ID = 1                  # 1 , 2 or 3
STATION_NAME = "Station " + str(STATION_ID)

BUS_TIMEOUT = 8                 # forget a bus after 8s of silence


# ---------------- OLED SETUP (two screens) ----------------
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)

screen1 = SSD1306_I2C(128, 64, i2c, addr=0x3C)   # arrival board
screen2 = SSD1306_I2C(128, 64, i2c, addr=0x3D)   # occupancy


def boot_message(line1, line2=""):
    for oled in (screen1, screen2):
        oled.fill(0)
        oled.text("STATION CORE", 0, 0)
        oled.text("----------------", 0, 10)
        oled.text(line1, 0, 30)
        oled.text(line2, 0, 42)
        oled.show()


# ---------------- WI-FI SETUP ----------------
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASS = ""


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        boot_message("Connecting WiFi")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print("WiFi connected:", wlan.ifconfig())
        boot_message("WiFi OK", wlan.ifconfig()[0])
        return True
    else:
        print("WiFi connection FAILED")
        boot_message("WiFi FAILED")
        return False


# ---------------- MQTT CONFIG ----------------
MQTT_BROKER = "broker.hivemq.com"
MQTT_CLIENT_ID = "station" + str(STATION_ID) + "_" + str(urandom.getrandbits(16))
MQTT_TOPIC = b"smartbus/+/data"


# ---------------- DATA MODEL ----------------
buses = {}          # buses[bus_num] = last state seen for THIS station
last_bus = None     # last bus that was standing here (kept on screen 2)


def parse_payload(payload_bytes):
    try:
        data = ujson.loads(payload_bytes)
    except (ValueError, TypeError) as e:
        print("JSON parse error:", e)
        return False

    station = int(data.get("station", 0))

    # only buses heading to / standing in THIS station
    if station != STATION_ID:
        return False

    bus_num = int(data.get("bus_num", 0))

    buses[bus_num] = {
        "bus_id": data.get("bus_id", "UNKNOWN"),
        "status": data.get("status", "Unknown"),
        "eta": int(data.get("eta", 0)),
        "leave_in": int(data.get("leave_in", 0)),
        "available": int(data.get("available", 0)),
        "occupied": int(data.get("occupied", 0)),
        "total": int(data.get("total", 0)),
        "t": time.ticks_ms()
    }

    return True


def age_seconds(entry):
    return time.ticks_diff(time.ticks_ms(), entry["t"]) // 1000


def live_count(entry, key):
    # keep counting down between MQTT messages
    left = entry[key] - age_seconds(entry)
    if left < 0:
        left = 0
    return left


def clean_old():
    for num in list(buses.keys()):
        if age_seconds(buses[num]) > BUS_TIMEOUT:
            del buses[num]


def get_bus_at_station():
    for num in buses:
        if buses[num]["status"] == "Arrived":
            return buses[num]
    return None


def get_next_incoming():
    best = None
    best_eta = 99999

    for num in buses:
        entry = buses[num]
        if entry["status"] == "Moving":
            eta = live_count(entry, "eta")
            if eta < best_eta:
                best_eta = eta
                best = entry

    return best, best_eta


# =========================================================
# SCREEN 1 - ARRIVAL BOARD
# =========================================================

def draw_screen1():

    bus = get_bus_at_station()
    nxt, nxt_eta = get_next_incoming()

    screen1.fill(0)
    screen1.text(STATION_NAME, 0, 0)
    screen1.text("----------------", 0, 10)

    if bus is not None:

        leave_in = live_count(bus, "leave_in")

        screen1.text(str(bus["bus_id"]) + " ARRIVED", 0, 20)
        screen1.text("leaving in " + str(leave_in) + "s", 0, 32)
        screen1.text("----------------", 0, 42)

        if nxt is not None:
            screen1.text(str(nxt["bus_id"]) + " in " + str(nxt_eta) + "s", 0, 54)
        else:
            screen1.text("no bus incoming", 0, 54)

    else:

        screen1.text("No bus at stop", 0, 22)

        if nxt is not None:
            screen1.text("Next: " + str(nxt["bus_id"]), 0, 40)
            screen1.text("arriving in " + str(nxt_eta) + "s", 0, 52)
        else:
            screen1.text("waiting for", 0, 40)
            screen1.text("bus data...", 0, 52)

    screen1.show()


# =========================================================
# SCREEN 2 - BUS OCCUPANCY
# =========================================================

def draw_screen2():

    global last_bus

    bus = get_bus_at_station()

    if bus is not None:
        last_bus = bus

    screen2.fill(0)
    screen2.text("BUS OCCUPANCY", 0, 0)
    screen2.text("----------------", 0, 10)

    if last_bus is None:
        screen2.text("No bus data", 0, 28)
        screen2.text("yet...", 0, 40)
        screen2.show()
        return

    screen2.text("Bus : " + str(last_bus["bus_id"]), 0, 20)
    screen2.text("Stat: " + str(last_bus["status"]), 0, 32)
    screen2.text("Free: " + str(last_bus["available"]) +
                 "/" + str(last_bus["total"]), 0, 44)
    screen2.text("Occ : " + str(last_bus["occupied"]), 0, 54)

    screen2.show()


def update_displays():
    clean_old()
    draw_screen1()
    draw_screen2()


# =========================================================
# MQTT
# =========================================================

def mqtt_callback(topic, msg):
    if parse_payload(msg):
        print("Update:", msg)


def connect_mqtt():
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=1883, keepalive=60)
    client.set_callback(mqtt_callback)
    client.connect()
    print("MQTT connected. Client ID:", MQTT_CLIENT_ID)
    client.subscribe(MQTT_TOPIC)
    print("Subscribed to topic:", MQTT_TOPIC)
    boot_message("MQTT Ready", "Listening...")
    return client


# ---------------- MAIN ----------------
if connect_wifi():
    time.sleep(1)
    mqtt_client = connect_mqtt()

    last_ping = time.ticks_ms()
    last_draw = time.ticks_ms()

    while True:

        try:
            mqtt_client.check_msg()

            if time.ticks_diff(time.ticks_ms(), last_ping) > 30000:
                mqtt_client.ping()
                last_ping = time.ticks_ms()

        except Exception as e:
            print("MQTT error:", e)
            time.sleep(2)
            try:
                mqtt_client = connect_mqtt()
                last_ping = time.ticks_ms()
            except Exception as e2:
                print("Reconnect failed:", e2)
                time.sleep(3)

        if time.ticks_diff(time.ticks_ms(), last_draw) >= 400:
            last_draw = time.ticks_ms()
            update_displays()

        time.sleep(0.05)
else:
    print("Cannot proceed without WiFi")