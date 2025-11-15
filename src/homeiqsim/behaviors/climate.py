"""Climate domain behavior engine."""

from datetime import timedelta
from typing import Any, Dict, List, Optional
import random

from .base import BehaviorEngine


class ClimateBehavior(BehaviorEngine):
    """Behavior engine for climate/thermostat entities."""

    HVAC_MODES = ["off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"]
    PRESET_MODES = ["none", "away", "eco", "boost", "comfort", "home", "sleep"]
    FAN_MODES = ["auto", "low", "medium", "high"]

    def __init__(self, *args, weather_driver=None, **kwargs):
        super().__init__("climate", *args, **kwargs)
        self.weather_driver = weather_driver

    def get_initial_state(self, entity_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get initial state for a climate entity."""
        config = config or {}

        # Supported features bitmask
        # 1=target temp, 2=target temp range, 4=target humidity, 8=fan mode,
        # 16=preset mode, 32=swing mode, 64=aux heat
        supported_features = 1 | 8 | 16  # temp, fan, preset

        attrs = {
            "friendly_name": config.get("name", entity_id.split(".")[1].replace("_", " ").title()),
            "supported_features": supported_features,
            "hvac_modes": config.get("hvac_modes", ["off", "heat", "cool", "auto"]),
            "preset_modes": self.PRESET_MODES,
            "fan_modes": self.FAN_MODES,
            "current_temperature": 20.0,
            "temperature": 21.0,  # Target temperature
            "min_temp": 10.0,
            "max_temp": 35.0,
            "temp_step": 0.5,
            "preset_mode": "none",
            "fan_mode": "auto",
        }

        # Some thermostats support humidity
        if config.get("humidity_control"):
            attrs["current_humidity"] = 50.0
            attrs["target_humidity"] = 50.0
            attrs["supported_features"] |= 4

        return {
            "state": "off",
            "attributes": attrs,
        }

    def start(self) -> None:
        """Start climate behavior simulation."""
        # Update current temperature and run HVAC logic
        self.event_loop.schedule_interval(
            interval=timedelta(minutes=1),
            callback=self._simulate_hvac,
            task_id=f"{self.domain}_hvac",
        )

    def _simulate_hvac(self) -> None:
        """Simulate HVAC operation."""
        for entity_id in self._entities:
            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            attrs = dict(state.attributes)

            # Get weather data for outdoor temp
            outdoor_temp = 15.0  # Default
            if self.weather_driver:
                weather_data = self.weather_driver(self.clock.now())
                outdoor_temp = weather_data.get("temp_c", 15.0)

            current_temp = attrs.get("current_temperature", 20.0)
            target_temp = attrs.get("temperature", 21.0)
            hvac_mode = state.state

            # Simulate temperature drift towards outdoor temp
            # Indoor temp drifts slowly toward outdoor temp
            drift_rate = 0.05
            thermal_drift = (outdoor_temp - current_temp) * drift_rate

            # HVAC effect
            hvac_effect = 0.0
            new_hvac_mode = hvac_mode

            if hvac_mode in ["heat", "heat_cool", "auto"]:
                if current_temp < target_temp - 0.5:
                    # Heating
                    hvac_effect = 0.3
                    new_hvac_mode = "heat"
                elif hvac_mode == "heat" and current_temp >= target_temp:
                    # Target reached
                    hvac_effect = 0.0
                    new_hvac_mode = "off" if hvac_mode == "heat" else hvac_mode

            if hvac_mode in ["cool", "heat_cool", "auto"]:
                if current_temp > target_temp + 0.5:
                    # Cooling
                    hvac_effect = -0.3
                    new_hvac_mode = "cool"
                elif hvac_mode == "cool" and current_temp <= target_temp:
                    # Target reached
                    hvac_effect = 0.0
                    new_hvac_mode = "off" if hvac_mode == "cool" else hvac_mode

            # Update temperature
            new_temp = current_temp + thermal_drift + hvac_effect
            # Add small random variation
            new_temp += random.gauss(0, 0.05)
            new_temp = round(new_temp, 1)

            attrs["current_temperature"] = new_temp

            # Update humidity if supported
            if "current_humidity" in attrs:
                current_humidity = attrs["current_humidity"]
                target_humidity = attrs.get("target_humidity", 50.0)

                # Humidity drifts
                if hvac_mode in ["heat", "cool"]:
                    # HVAC tends to dehumidify
                    humidity_change = -0.2
                else:
                    # Drift toward ambient
                    humidity_change = random.gauss(0, 0.1)

                new_humidity = current_humidity + humidity_change
                new_humidity = max(20, min(80, round(new_humidity, 1)))
                attrs["current_humidity"] = new_humidity

            self._update_state(entity_id, new_hvac_mode, attrs)

    def _service_set_temperature(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle climate.set_temperature service."""
        state = self.state_manager.get_state(entity_id)
        if not state:
            return

        attrs = dict(state.attributes)

        if "temperature" in data:
            temp = float(data["temperature"])
            temp = max(attrs["min_temp"], min(attrs["max_temp"], temp))
            attrs["temperature"] = temp

        # Optionally set HVAC mode
        new_mode = state.state
        if "hvac_mode" in data:
            if data["hvac_mode"] in attrs["hvac_modes"]:
                new_mode = data["hvac_mode"]

        self._update_state(entity_id, new_mode, attrs)

    def _service_set_hvac_mode(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle climate.set_hvac_mode service."""
        state = self.state_manager.get_state(entity_id)
        if not state:
            return

        hvac_mode = data.get("hvac_mode")
        if hvac_mode and hvac_mode in state.attributes.get("hvac_modes", []):
            self._update_state(entity_id, hvac_mode, state.attributes)

    def _service_set_preset_mode(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle climate.set_preset_mode service."""
        state = self.state_manager.get_state(entity_id)
        if not state:
            return

        preset_mode = data.get("preset_mode")
        if preset_mode and preset_mode in self.PRESET_MODES:
            attrs = dict(state.attributes)
            attrs["preset_mode"] = preset_mode

            # Adjust target temperature based on preset
            if preset_mode == "away":
                attrs["temperature"] = 18.0  # Eco mode
            elif preset_mode == "eco":
                attrs["temperature"] = 19.0
            elif preset_mode == "boost":
                attrs["temperature"] = 24.0
            elif preset_mode == "comfort":
                attrs["temperature"] = 21.0
            elif preset_mode == "sleep":
                attrs["temperature"] = 19.0

            self._update_state(entity_id, state.state, attrs)

    def _service_set_fan_mode(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle climate.set_fan_mode service."""
        state = self.state_manager.get_state(entity_id)
        if not state:
            return

        fan_mode = data.get("fan_mode")
        if fan_mode and fan_mode in self.FAN_MODES:
            attrs = dict(state.attributes)
            attrs["fan_mode"] = fan_mode
            self._update_state(entity_id, state.state, attrs)

    def _service_set_humidity(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle climate.set_humidity service."""
        state = self.state_manager.get_state(entity_id)
        if not state or "target_humidity" not in state.attributes:
            return

        humidity = data.get("humidity")
        if humidity is not None:
            attrs = dict(state.attributes)
            attrs["target_humidity"] = max(20, min(80, float(humidity)))
            self._update_state(entity_id, state.state, attrs)
