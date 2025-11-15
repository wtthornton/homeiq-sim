"""Switch domain behavior engine."""

from datetime import timedelta
from typing import Any, Dict, Optional
import random

from .base import BehaviorEngine


class SwitchBehavior(BehaviorEngine):
    """Behavior engine for switch entities."""

    def __init__(self, *args, **kwargs):
        super().__init__("switch", *args, **kwargs)

    def get_initial_state(self, entity_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get initial state for a switch."""
        config = config or {}

        attrs = {
            "friendly_name": config.get("name", entity_id.split(".")[1].replace("_", " ").title()),
        }

        # Some switches might have power monitoring
        if config.get("power_monitoring"):
            attrs["current_power_w"] = 0.0

        return {
            "state": config.get("initial_state", "off"),
            "attributes": attrs,
        }

    def start(self) -> None:
        """Start switch behavior simulation."""
        # Schedule periodic updates for power monitoring
        self.event_loop.schedule_interval(
            interval=timedelta(seconds=30),
            callback=self._update_power_monitoring,
            task_id=f"{self.domain}_power_monitoring",
        )

    def _update_power_monitoring(self) -> None:
        """Update power monitoring for switches that support it."""
        for entity_id in self._entities:
            state = self.state_manager.get_state(entity_id)
            if not state or "current_power_w" not in state.attributes:
                continue

            if state.state == "on":
                # Simulate power draw with some variation
                config = self.get_entity_config(entity_id)
                base_power = config.get("rated_power", 10.0)
                variation = random.uniform(0.9, 1.1)
                power = base_power * variation
            else:
                # Small phantom draw when off
                power = random.uniform(0.0, 0.5)

            attrs = dict(state.attributes)
            attrs["current_power_w"] = round(power, 1)
            self._update_state(entity_id, state.state, attrs)

    def _service_turn_on(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle switch.turn_on service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            self._update_state(entity_id, "on", state.attributes)

    def _service_turn_off(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle switch.turn_off service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            self._update_state(entity_id, "off", state.attributes)

    def _service_toggle(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle switch.toggle service."""
        state = self.state_manager.get_state(entity_id)
        if not state:
            return

        new_state = "off" if state.state == "on" else "on"
        self._update_state(entity_id, new_state, state.attributes)
