# Smart Bus Monitoring System

A real-time IoT-based system for tracking buses and stations, built as a course project simulated on [Wokwi](https://wokwi.com).

## Overview

Passengers often don't know when the next bus will arrive or whether it will have free seats. Station and city management also lack a unified, real-time view of the entire bus fleet.

This project solves that by connecting three main components over MQTT:

- **Buses** – simulate 3 buses (ESP32 + MicroPython) that move automatically between 3 stations on a timed schedule, track free/occupied seats, and publish live status data.
- **Stations** – simulate 3 stations (ESP32 + two OLED screens) that subscribe to the bus data and display an arrival board and occupancy details for passengers.
- **Dashboard** – a Node-RED dashboard giving administrators a full, real-time overview of the whole fleet (fleet status, station boards, per-bus occupancy, and occupancy history over time).

## Project structure

```
smart-bus-monitoring-system/
├── buses/          # MicroPython code for Bus 1, Bus 2, Bus 3 (ESP32)
├── station/         # MicroPython code for Station 1, Station 2, Station 3 (ESP32)
├── dashboard/        # Node-RED flow (exported as JSON) for the admin dashboard
├── images/          # Screenshots of the dashboard, Wokwi simulation, and wiring
└── README.md
```

## How it works

1. Each bus publishes its status (station, ETA, free/occupied seats) as a JSON message over MQTT (`broker.hivemq.com`), on its own topic (`smartbus/busN/data`).
2. Each station subscribes to all bus topics, filters for buses relevant to its own station, and updates its two OLED screens (arrival board + occupancy).
3. The dashboard subscribes to all bus data as well, showing a fleet-wide overview for administrators.

## Running the simulation

1. Open [Wokwi](https://wokwi.com) and create a new ESP32 project for each bus / station.
2. Copy the corresponding code from `buses/` or `station/` into `main.py`.
3. For buses, only `BUS_NUM` changes (1, 2, or 3). For stations, only `STATION_ID` changes (1, 2, or 3).
4. Run the simulation — buses and stations will connect to Wi-Fi and MQTT automatically.

## Project Demo

[View Project Demo on Google Drive](https://drive.google.com/file/d/1GUh8mPDBuYVtVQvbYrPaT2XAC3OKnns1/view?usp=drivesdk)

## Future work

- Integrate the dashboard into a mobile app with separate Admin and User views
- Use real GPS tracking instead of simulated movement
- Add push notifications for bus arrivals

## Team

- [ِAbdullah Nagy Abdullah -
Loai Ahmed Ali -
Marawan Ahmed Mohamed -
Rana Hany Hegazy -
Sohila Talaat Mohamed
]
