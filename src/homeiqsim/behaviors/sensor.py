"""Sensor domain behavior engine."""

from datetime import timedelta
from typing import Any, Dict, Optional
import random
import math

from .base import BehaviorEngine


class SensorBehavior(BehaviorEngine):
    """Behavior engine for sensor entities."""

    def __init__(self, *args, weather_driver=None, **kwargs):
        super().__init__("sensor", *args, **kwargs)
        self.weather_driver = weather_driver

    def get_initial_state(self, entity_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get initial state for a sensor."""
        config = config or {}
        device_class = config.get("device_class", "")

        attrs = {
            "friendly_name": config.get("name", entity_id.split(".")[1].replace("_", " ").title()),
        }

        if device_class:
            attrs["device_class"] = device_class

        # Add unit of measurement based on device class
        unit_map = {
            "temperature": "°C",
            "humidity": "%",
            "pressure": "hPa",
            "battery": "%",
            "power": "W",
            "energy": "kWh",
            "voltage": "V",
            "current": "A",
            "illuminance": "lx",
            "pm25": "µg/m³",
            "co2": "ppm",
        }

        if device_class in unit_map:
            attrs["unit_of_measurement"] = unit_map[device_class]

        # State class for statistics
        if device_class in ["energy"]:
            attrs["state_class"] = "total_increasing"
        elif device_class in ["power", "voltage", "current", "temperature", "humidity", "pressure"]:
            attrs["state_class"] = "measurement"

        # Initial value based on device class
        initial_values = {
            "temperature": 20.0,
            "humidity": 50.0,
            "pressure": 1013.0,
            "battery": 100.0,
            "power": 0.0,
            "energy": 0.0,
            "voltage": 120.0,
            "current": 0.0,
            "illuminance": 0,
            "pm25": 5,
            "co2": 400,
        }

        initial_state = initial_values.get(device_class, 0)

        # Battery powered sensors
        if config.get("battery_powered", device_class == "battery"):
            attrs["battery_level"] = random.randint(80, 100)

        return {
            "state": str(initial_state),
            "attributes": attrs,
        }

    def start(self) -> None:
        """Start sensor behavior simulation."""
        # Update temperature/humidity sensors
        self.event_loop.schedule_interval(
            interval=timedelta(minutes=1),
            callback=self._update_environmental_sensors,
            task_id=f"{self.domain}_environmental",
        )

        # Update power/energy sensors
        self.event_loop.schedule_interval(
            interval=timedelta(seconds=10),
            callback=self._update_power_sensors,
            task_id=f"{self.domain}_power",
        )

        # Update misc sensors
        self.event_loop.schedule_interval(
            interval=timedelta(seconds=30),
            callback=self._update_misc_sensors,
            task_id=f"{self.domain}_misc",
        )

    def _update_environmental_sensors(self) -> None:
        """Update temperature, humidity, pressure sensors."""
        for entity_id in self._entities:
            config = self.get_entity_config(entity_id)
            device_class = config.get("device_class")

            if device_class not in ["temperature", "humidity", "pressure"]:
                continue

            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            try:
                current_value = float(state.state)
            except (ValueError, TypeError):
                current_value = 20.0

            # Get weather data if available
            weather_data = None
            if self.weather_driver:
                now = self.clock.now()
                weather_data = self.weather_driver(now)

            if device_class == "temperature":
                if weather_data and config.get("outdoor", False):
                    # Outdoor sensor follows weather
                    target = weather_data.get("temp_c", 20.0)
                else:
                    # Indoor sensor - relatively stable
                    target = 21.0 + random.gauss(0, 0.5)

                # Smooth changes
                new_value = current_value + (target - current_value) * 0.1
                new_value += random.gauss(0, 0.1)
                new_value = round(new_value, 1)

            elif device_class == "humidity":
                if weather_data and config.get("outdoor", False):
                    target = weather_data.get("rel_humidity", 50.0)
                else:
                    target = 45.0 + random.gauss(0, 5)

                new_value = current_value + (target - current_value) * 0.1
                new_value += random.gauss(0, 1)
                new_value = max(0, min(100, round(new_value, 1)))

            elif device_class == "pressure":
                # Pressure changes slowly
                new_value = current_value + random.gauss(0, 0.5)
                new_value = max(950, min(1050, round(new_value, 1)))

            else:
                continue

            self._update_state(entity_id, str(new_value), state.attributes)

    def _update_power_sensors(self) -> None:
        """Update power and energy sensors."""
        for entity_id in self._entities:
            config = self.get_entity_config(entity_id)
            device_class = config.get("device_class")

            if device_class not in ["power", "energy", "voltage", "current"]:
                continue

            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            try:
                current_value = float(state.state)
            except (ValueError, TypeError):
                current_value = 0.0

            if device_class == "power":
                # Check if linked to a device
                linked_device = config.get("linked_entity")
                if linked_device:
                    device_state = self.state_manager.get_state(linked_device)
                    if device_state and device_state.state == "on":
                        # Device on - use rated power with variation
                        rated = config.get("rated_power", 10.0)
                        new_value = rated * random.uniform(0.9, 1.1)
                    else:
                        # Device off - phantom power
                        new_value = random.uniform(0, 0.5)
                else:
                    # Simulate varying load
                    new_value = current_value + random.gauss(0, 5)
                    new_value = max(0, new_value)

                new_value = round(new_value, 1)

            elif device_class == "energy":
                # Energy accumulates
                # Get linked power sensor if exists
                power_sensor = config.get("power_sensor")
                if power_sensor:
                    power_state = self.state_manager.get_state(power_sensor)
                    if power_state:
                        try:
                            power = float(power_state.state)
                            # Add energy (10 sec interval = 1/360 hour)
                            new_value = current_value + (power / 360000.0)
                        except (ValueError, TypeError):
                            new_value = current_value
                    else:
                        new_value = current_value
                else:
                    new_value = current_value

                new_value = round(new_value, 3)

            elif device_class == "voltage":
                # Voltage is relatively stable
                new_value = 120.0 + random.gauss(0, 0.5)
                new_value = round(new_value, 1)

            elif device_class == "current":
                # Current based on power (if linked)
                power_sensor = config.get("power_sensor")
                if power_sensor:
                    power_state = self.state_manager.get_state(power_sensor)
                    if power_state:
                        try:
                            power = float(power_state.state)
                            new_value = power / 120.0  # I = P/V
                        except (ValueError, TypeError):
                            new_value = 0.0
                    else:
                        new_value = 0.0
                else:
                    new_value = random.uniform(0, 1)

                new_value = round(new_value, 2)

            else:
                continue

            self._update_state(entity_id, str(new_value), state.attributes)

    def _update_misc_sensors(self) -> None:
        """Update other sensor types."""
        current_hour = self.clock.now().hour

        for entity_id in self._entities:
            config = self.get_entity_config(entity_id)
            device_class = config.get("device_class")

            if device_class not in ["illuminance", "pm25", "co2"]:
                continue

            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            try:
                current_value = float(state.state)
            except (ValueError, TypeError):
                current_value = 0.0

            if device_class == "illuminance":
                # Light level varies by time of day
                if 6 <= current_hour < 8:
                    target = 500
                elif 8 <= current_hour < 18:
                    target = 1000
                elif 18 <= current_hour < 21:
                    target = 300
                else:
                    target = 10

                new_value = current_value + (target - current_value) * 0.2
                new_value += random.gauss(0, 50)
                new_value = max(0, round(new_value))

            elif device_class == "pm25":
                # PM2.5 varies, generally low
                new_value = max(0, 5 + random.gauss(0, 2))
                new_value = round(new_value, 1)

            elif device_class == "co2":
                # CO2 varies with occupancy
                # TODO: Link to occupancy
                new_value = current_value + random.gauss(0, 20)
                new_value = max(400, min(2000, round(new_value)))

            else:
                continue

            self._update_state(entity_id, str(new_value), state.attributes)
