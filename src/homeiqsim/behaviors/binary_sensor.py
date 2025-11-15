"""Binary sensor domain behavior engine."""

from datetime import timedelta
from typing import Any, Dict, Optional
import random

from .base import BehaviorEngine


class BinarySensorBehavior(BehaviorEngine):
    """Behavior engine for binary_sensor entities."""

    def __init__(self, *args, **kwargs):
        super().__init__("binary_sensor", *args, **kwargs)
        self._occupancy_state = {}  # Tracks occupancy per area

    def get_initial_state(self, entity_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get initial state for a binary sensor."""
        config = config or {}
        device_class = config.get("device_class", "motion")

        attrs = {
            "friendly_name": config.get("name", entity_id.split(".")[1].replace("_", " ").title()),
            "device_class": device_class,
        }

        # Battery powered sensors have battery level
        if config.get("battery_powered", True):
            attrs["battery_level"] = random.randint(80, 100)

        return {
            "state": "off",
            "attributes": attrs,
        }

    def start(self) -> None:
        """Start binary sensor behavior simulation."""
        # Motion sensors - simulate occupancy patterns
        self.event_loop.schedule_interval(
            interval=timedelta(seconds=30),
            callback=self._simulate_motion,
            task_id=f"{self.domain}_motion",
        )

        # Door/window sensors - simulate opening/closing
        self.event_loop.schedule_interval(
            interval=timedelta(minutes=10),
            callback=self._simulate_door_window,
            task_id=f"{self.domain}_door_window",
        )

        # Battery level updates
        self.event_loop.schedule_interval(
            interval=timedelta(hours=1),
            callback=self._update_battery,
            task_id=f"{self.domain}_battery",
        )

    def set_occupancy(self, area: str, occupied: bool) -> None:
        """Set occupancy state for an area.

        Args:
            area: Area name (e.g., 'living_room', 'bedroom')
            occupied: Whether the area is occupied
        """
        self._occupancy_state[area] = occupied

        # Trigger motion sensors in the area
        for entity_id in self._entities:
            config = self.get_entity_config(entity_id)
            if config.get("device_class") == "motion" and config.get("area") == area:
                new_state = "on" if occupied else "off"
                state = self.state_manager.get_state(entity_id)
                if state:
                    self._update_state(entity_id, new_state, state.attributes)

    def _simulate_motion(self) -> None:
        """Simulate motion sensor triggers."""
        current_hour = self.clock.now().hour

        # Activity levels by time of day
        if 6 <= current_hour < 9:  # Morning
            activity = 0.5
        elif 9 <= current_hour < 12:  # Late morning
            activity = 0.3
        elif 12 <= current_hour < 13:  # Lunch
            activity = 0.4
        elif 13 <= current_hour < 17:  # Afternoon
            activity = 0.2
        elif 17 <= current_hour < 21:  # Evening
            activity = 0.6
        elif 21 <= current_hour < 23:  # Late evening
            activity = 0.4
        else:  # Night
            activity = 0.05

        for entity_id in self._entities:
            config = self.get_entity_config(entity_id)
            if config.get("device_class") != "motion":
                continue

            # Check if controlled by occupancy
            area = config.get("area")
            if area and area in self._occupancy_state:
                continue  # Controlled externally

            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            # Randomly trigger based on activity
            if state.state == "off":
                if random.random() < activity * 0.2:  # Trigger on
                    self._update_state(entity_id, "on", state.attributes)
            else:
                # Motion sensors auto-clear after timeout
                if random.random() < 0.3:  # 30% chance to clear
                    self._update_state(entity_id, "off", state.attributes)

    def _simulate_door_window(self) -> None:
        """Simulate door and window sensors."""
        for entity_id in self._entities:
            config = self.get_entity_config(entity_id)
            device_class = config.get("device_class")

            if device_class not in ["door", "window", "opening"]:
                continue

            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            # Doors open/close more frequently than windows
            if device_class == "door":
                change_prob = 0.05
            else:
                change_prob = 0.01

            if random.random() < change_prob:
                new_state = "off" if state.state == "on" else "on"
                self._update_state(entity_id, new_state, state.attributes)

    def _update_battery(self) -> None:
        """Update battery levels for battery-powered sensors."""
        for entity_id in self._entities:
            state = self.state_manager.get_state(entity_id)
            if not state or "battery_level" not in state.attributes:
                continue

            # Slowly drain battery (0.1% per hour on average)
            current_battery = state.attributes["battery_level"]
            new_battery = max(0, current_battery - random.uniform(0.0, 0.2))

            attrs = dict(state.attributes)
            attrs["battery_level"] = round(new_battery, 1)
            self._update_state(entity_id, state.state, attrs)

    # Binary sensors typically don't have services, they're read-only
    # But we can add a test service for debugging
    def _service_test(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Test service to manually trigger a binary sensor."""
        state = self.state_manager.get_state(entity_id)
        if state:
            new_state = data.get("state", "on")
            self._update_state(entity_id, new_state, state.attributes)
