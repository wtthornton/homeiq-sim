"""Light domain behavior engine."""

from datetime import timedelta
from typing import Any, Dict, Optional
import random

from .base import BehaviorEngine


class LightBehavior(BehaviorEngine):
    """Behavior engine for light entities."""

    def __init__(self, *args, **kwargs):
        super().__init__("light", *args, **kwargs)
        self._motion_triggers = {}  # Maps lights to motion sensors

    def get_initial_state(self, entity_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get initial state for a light."""
        config = config or {}

        attrs = {
            "friendly_name": config.get("name", entity_id.split(".")[1].replace("_", " ").title()),
        }

        # Add capability attributes based on config
        if config.get("brightness", True):
            attrs["brightness"] = 255
            attrs["supported_features"] = 1  # Brightness support

        if config.get("color_temp"):
            attrs["color_temp"] = 370
            attrs["min_mireds"] = 153
            attrs["max_mireds"] = 500
            attrs["supported_features"] = attrs.get("supported_features", 0) | 2

        if config.get("rgb_color"):
            attrs["rgb_color"] = [255, 255, 255]
            attrs["supported_features"] = attrs.get("supported_features", 0) | 16

        if config.get("effect"):
            attrs["effect_list"] = ["none", "colorloop", "random"]
            attrs["effect"] = "none"
            attrs["supported_features"] = attrs.get("supported_features", 0) | 4

        return {
            "state": "off",
            "attributes": attrs,
        }

    def start(self) -> None:
        """Start light behavior simulation."""
        # Schedule periodic random state changes (simulate occupancy)
        self.event_loop.schedule_interval(
            interval=timedelta(minutes=5),
            callback=self._simulate_usage,
            task_id=f"{self.domain}_simulate_usage",
        )

    def _simulate_usage(self) -> None:
        """Simulate random light usage based on time of day."""
        current_hour = self.clock.now().hour

        # Determine activity level based on time
        if 6 <= current_hour < 9:  # Morning
            activity = 0.4
        elif 9 <= current_hour < 17:  # Day
            activity = 0.2
        elif 17 <= current_hour < 23:  # Evening
            activity = 0.6
        else:  # Night
            activity = 0.1

        for entity_id in self._entities:
            config = self.get_entity_config(entity_id)

            # Skip if controlled by automation
            if config.get("automated"):
                continue

            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            # Randomly toggle based on activity level
            if random.random() < activity * 0.1:  # 10% of activity level per 5min
                new_state = "off" if state.state == "on" else "on"
                attrs = dict(state.attributes)

                if new_state == "on" and "brightness" in attrs:
                    # Random brightness when turning on
                    attrs["brightness"] = random.randint(128, 255)

                self._update_state(entity_id, new_state, attrs)

    def link_motion_sensor(self, light_id: str, motion_sensor_id: str) -> None:
        """Link a light to a motion sensor for automatic control.

        Args:
            light_id: The light entity ID
            motion_sensor_id: The motion sensor entity ID
        """
        self._motion_triggers[light_id] = motion_sensor_id

        # Mark as automated
        config = self.get_entity_config(light_id)
        config["automated"] = True
        self._entity_config[light_id] = config

    def _service_turn_on(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle light.turn_on service."""
        state = self.state_manager.get_state(entity_id)
        if not state:
            return

        attrs = dict(state.attributes)

        # Update brightness if provided
        if "brightness" in data:
            attrs["brightness"] = min(255, max(0, int(data["brightness"])))

        # Update color temp if provided
        if "color_temp" in data and "color_temp" in attrs:
            attrs["color_temp"] = min(500, max(153, int(data["color_temp"])))

        # Update RGB color if provided
        if "rgb_color" in data and "rgb_color" in attrs:
            attrs["rgb_color"] = data["rgb_color"]

        # Update effect if provided
        if "effect" in data and "effect_list" in attrs:
            if data["effect"] in attrs["effect_list"]:
                attrs["effect"] = data["effect"]

        # Brightness defaults to max if not specified and light supports it
        if "brightness" in attrs and "brightness" not in data:
            attrs["brightness"] = 255

        self._update_state(entity_id, "on", attrs)

    def _service_turn_off(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle light.turn_off service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            self._update_state(entity_id, "off", state.attributes)

    def _service_toggle(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle light.toggle service."""
        state = self.state_manager.get_state(entity_id)
        if not state:
            return

        if state.state == "on":
            self._service_turn_off(entity_id, data)
        else:
            self._service_turn_on(entity_id, data)
