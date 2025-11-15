"""Cover domain behavior engine (blinds, shades, garage doors)."""

from datetime import timedelta
from typing import Any, Dict, Optional
import random

from .base import BehaviorEngine


class CoverBehavior(BehaviorEngine):
    """Behavior engine for cover entities."""

    def __init__(self, *args, **kwargs):
        super().__init__("cover", *args, **kwargs)

    def get_initial_state(self, entity_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get initial state for a cover."""
        config = config or {}
        device_class = config.get("device_class", "blind")  # blind, shade, garage, door, window

        attrs = {
            "friendly_name": config.get("name", entity_id.split(".")[1].replace("_", " ").title()),
            "device_class": device_class,
            "supported_features": 15,  # open, close, stop, position
            "current_position": 0,  # 0 = closed, 100 = open
        }

        # Some covers support tilt
        if config.get("tilt_support", device_class in ["blind"]):
            attrs["supported_features"] |= 128
            attrs["current_tilt_position"] = 0

        return {
            "state": "closed",
            "attributes": attrs,
        }

    def start(self) -> None:
        """Start cover behavior simulation."""
        # Simulate automatic opening/closing based on time
        self.event_loop.schedule_interval(
            interval=timedelta(minutes=30),
            callback=self._simulate_automatic_control,
            task_id=f"{self.domain}_auto",
        )

    def _simulate_automatic_control(self) -> None:
        """Simulate automatic cover control based on time of day."""
        current_hour = self.clock.now().hour

        for entity_id in self._entities:
            config = self.get_entity_config(entity_id)
            if config.get("manual_only"):
                continue

            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            device_class = state.attributes.get("device_class", "blind")

            # Blinds/shades follow sun patterns
            if device_class in ["blind", "shade"]:
                if 6 <= current_hour < 8:  # Morning - open
                    if random.random() < 0.3:
                        self._set_position(entity_id, 100)
                elif 17 <= current_hour < 19:  # Evening - close
                    if random.random() < 0.3:
                        self._set_position(entity_id, 0)

            # Garage doors have different patterns
            elif device_class == "garage":
                # Garage doors open/close with occupancy
                if current_hour in [8, 9, 17, 18]:  # Commute times
                    if random.random() < 0.1:
                        current_pos = state.attributes.get("current_position", 0)
                        new_pos = 100 if current_pos == 0 else 0
                        self._set_position(entity_id, new_pos)

    def _set_position(self, entity_id: str, position: int) -> None:
        """Set cover position.

        Args:
            entity_id: The entity ID
            position: Target position (0-100)
        """
        position = max(0, min(100, position))
        state = self.state_manager.get_state(entity_id)
        if not state:
            return

        attrs = dict(state.attributes)
        attrs["current_position"] = position

        # Determine state based on position
        if position == 0:
            new_state = "closed"
        elif position == 100:
            new_state = "open"
        else:
            new_state = "opening" if position > attrs.get("current_position", 0) else "closing"

        self._update_state(entity_id, new_state, attrs)

    def _service_open_cover(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle cover.open_cover service."""
        self._set_position(entity_id, 100)

    def _service_close_cover(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle cover.close_cover service."""
        self._set_position(entity_id, 0)

    def _service_stop_cover(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle cover.stop_cover service."""
        state = self.state_manager.get_state(entity_id)
        if state and state.state in ["opening", "closing"]:
            # Just mark as stopped
            self._update_state(entity_id, "open", state.attributes)

    def _service_set_cover_position(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle cover.set_cover_position service."""
        position = data.get("position")
        if position is not None:
            self._set_position(entity_id, int(position))

    def _service_set_cover_tilt_position(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle cover.set_cover_tilt_position service."""
        tilt_position = data.get("tilt_position")
        if tilt_position is not None:
            state = self.state_manager.get_state(entity_id)
            if state and "current_tilt_position" in state.attributes:
                attrs = dict(state.attributes)
                attrs["current_tilt_position"] = max(0, min(100, int(tilt_position)))
                self._update_state(entity_id, state.state, attrs)
