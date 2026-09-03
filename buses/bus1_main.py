# ============================================================
# SMART BUS - Auto route with timed schedule
# Route loop: Station 1 -> Station 2 -> Station 3 -> Station 1
# ============================================================

import network
import time
from machine import Pin
from umqtt.simple import MQTTClient


# =========================================================
# CONFIGURATION  <-- ONLY THIS NUMBER CHANGES PER BUS
# =========================================================

BUS_NUM = 1                     # 1 , 2 or 3

BUS_ID = "BUS_" + str(BUS_NUM)
BUS_KEY = "bus" + str(BUS_NUM)


# =========================================================
# TIMING TABLE (seconds)
# travel = time moving between two stations
# dwell  = time standing in the station before leaving
# =========================================================

TRAVEL_TIME = {1: 30, 2: 45, 3: 60}
DWELL_TIME = {1: 10, 2: 12, 3: 15}

TRAVEL = TRAVEL_TIME[BUS_NUM]
DWELL = DWELL_TIME[BUS_NUM]

TOTAL_STATIONS = 3


# =========================================================
# MQTT
# =========================================================

SERVER = "broker.hivemq.com"
PORT = 1883

DATA_TOPIC = ("smartbus/" + BUS_KEY + "/data").encode()
CLIENT_ID = ("smartbus_" + BUS_KEY + "_auto").encode()


# =========================================================
# SEAT BUTTON PINS
# =========================================================

SEAT_PINS = [
    13, 12, 14, 27, 26,
    25, 33, 32, 17, 15
]

ARRIVAL_BUTTON_PIN = 4          # force arrive now
DEPARTURE_BUTTON_PIN = 5        # force leave now


# =========================================================
# WIFI
# =========================================================

WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

print("Connecting to WiFi...")

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(WIFI_SSID, WIFI_PASSWORD)

while not wifi.isconnected():
    print("Waiting for WiFi...")
    time.sleep(1)

print("WiFi connected!")
print("IP:", wifi.ifconfig()[0])


# =========================================================
# CONNECT TO MQTT
# =========================================================

client = MQTTClient(CLIENT_ID, SERVER, port=PORT, keepalive=60)


def mqtt_connect():
    print("Connecting to MQTT...")
    client.connect()
    print("MQTT connected -> topic:", DATA_TOPIC)


mqtt_connect()


# =========================================================
# BUTTONS
# =========================================================

seats = [Pin(pin, Pin.IN, Pin.PULL_UP) for pin in SEAT_PINS]

arrival_button = Pin(ARRIVAL_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
departure_button = Pin(DEPARTURE_BUTTON_PIN, Pin.IN, Pin.PULL_UP)


# =========================================================
# SEATS
# =========================================================

def get_free_seats():

    free = 0

    for seat in seats:

        # PULL_UP:
        # 0 = pressed = occupied
        # 1 = released = free

        if seat.value() == 1:
            free += 1

    return free


# =========================================================
# ROUTE STATE
# =========================================================

# Bus N starts by heading to Station N, so the 3 buses
# are spread over the line instead of stacking together.

target_station = BUS_NUM
bus_status = "Moving"
seconds_left = TRAVEL


def next_station(current):
    nxt = current + 1
    if nxt > TOTAL_STATIONS:
        nxt = 1
    return nxt


# =========================================================
# PUBLISH  (one topic, one JSON message)
# =========================================================

def publish_bus_data():

    total_seats = len(seats)
    available = get_free_seats()
    occupied = total_seats - available

    if bus_status == "Moving":
        eta = seconds_left
        leave_in = 0
    else:
        eta = 0
        leave_in = seconds_left

    data = (
        '{"bus_id":"' + BUS_ID +
        '","bus_num":' + str(BUS_NUM) +
        ',"status":"' + bus_status +
        '","station":' + str(target_station) +
        ',"eta":' + str(eta) +
        ',"leave_in":' + str(leave_in) +
        ',"available":' + str(available) +
        ',"occupied":' + str(occupied) +
        ',"total":' + str(total_seats) +
        '}'
    )

    try:
        client.publish(DATA_TOPIC, data)
    except Exception as e:
        print("Publish failed:", e)
        try:
            mqtt_connect()
            client.publish(DATA_TOPIC, data)
        except Exception as e2:
            print("Reconnect failed:", e2)


def print_line():

    total_seats = len(seats)
    available = get_free_seats()
    occupied = total_seats - available

    if bus_status == "Moving":
        print(BUS_ID, "| Moving -> Station", target_station,
              "| arriving in", seconds_left, "s",
              "| free", available, "| occ", occupied)
    else:
        print(BUS_ID, "| ARRIVED at Station", target_station,
              "| leaving in", seconds_left, "s",
              "| free", available, "| occ", occupied)


# =========================================================
# STARTUP
# =========================================================

print()
print("==============================")
print("SMART BUS SYSTEM - AUTO ROUTE")
print("==============================")
print("Bus:", BUS_ID)
print("Total Seats:", len(seats))
print("Travel time:", TRAVEL, "s")
print("Dwell time:", DWELL, "s")
print("First stop: Station", target_station)
print("Topic:", DATA_TOPIC)
print("==============================")

publish_bus_data()


# =========================================================
# MAIN LOOP
# =========================================================

last_arrival_state = 1
last_departure_state = 1
last_occupied = len(seats) - get_free_seats()

last_tick = time.ticks_ms()

while True:

    now = time.ticks_ms()

    current_arrival_state = arrival_button.value()
    current_departure_state = departure_button.value()

    # =====================================================
    # MANUAL OVERRIDE - ARRIVE NOW
    # =====================================================

    if last_arrival_state == 1 and current_arrival_state == 0:
        if bus_status == "Moving":
            print()
            print("ARRIVAL BUTTON PRESSED - skipping travel time")
            seconds_left = 0

    # =====================================================
    # MANUAL OVERRIDE - LEAVE NOW
    # =====================================================

    if last_departure_state == 1 and current_departure_state == 0:
        if bus_status == "Arrived":
            print()
            print("MOVING BUTTON PRESSED - leaving early")
            seconds_left = 0

    # =====================================================
    # ONE SECOND TICK
    # =====================================================

    if time.ticks_diff(now, last_tick) >= 1000:

        last_tick = now

        if seconds_left > 0:
            seconds_left -= 1

        if seconds_left <= 0:

            if bus_status == "Moving":
                # reached the station
                bus_status = "Arrived"
                seconds_left = DWELL

                print()
                print("### " + BUS_ID + " ARRIVED AT STATION",
                      target_station, "###")

            else:
                # leaving the station
                target_station = next_station(target_station)
                bus_status = "Moving"
                seconds_left = TRAVEL

                print()
                print("### " + BUS_ID + " DEPARTED -> STATION",
                      target_station, "###")

        print_line()
        publish_bus_data()

    # =====================================================
    # SEAT CHANGE -> PUBLISH IMMEDIATELY
    # =====================================================

    occupied_now = len(seats) - get_free_seats()

    if occupied_now != last_occupied:
        last_occupied = occupied_now
        print("Seat change detected")
        publish_bus_data()
        time.sleep(0.2)

    last_arrival_state = current_arrival_state
    last_departure_state = current_departure_state

    time.sleep(0.05)
