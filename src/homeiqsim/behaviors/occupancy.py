"""Occupancy simulation for realistic home presence patterns."""

from datetime import timedelta, time
from typing import Any, Dict, List, Optional
import random

from ..runtime.state import StateManager
from ..runtime.clock import SimulationClock
from ..runtime.loop import EventLoop


class OccupancySimulator:
    """Simulates realistic occupancy patterns for a home."""

    def __init__(
        self,
        home_id: str,
        state_manager: StateManager,
        clock: SimulationClock,
        event_loop: EventLoop,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize occupancy simulator.

        Args:
            home_id: Home identifier
            state_manager: State manager instance
            clock: Simulation clock
            event_loop: Event loop for scheduling
            config: Configuration dict
        """
        self.home_id = home_id
        self.state_manager = state_manager
        self.clock = clock
        self.event_loop = event_loop
        self.config = config or {}

        # Occupancy state
        self.is_home = True
        self.is_sleeping = False
        self.active_areas: List[str] = []

        # Configuration
        self.has_kids = self.config.get("has_kids", False)
        self.wfh_ratio = self.config.get("wfh_ratio", 0.3)  # Work from home days
        self.shift_worker = self.config.get("shift_worker", False)

        # Schedule
        self.wake_time = time(6, 30)
        self.sleep_time = time(22, 30)
        self.leave_home_time = time(8, 0)
        self.return_home_time = time(17, 30)

    def start(self) -> None:
        """Start occupancy simulation."""
        # Schedule daily routine checks
        self.event_loop.schedule_interval(
            interval=timedelta(minutes=15),
            callback=self._update_occupancy,
            task_id=f"occupancy_{self.home_id}",
        )

    def _update_occupancy(self) -> None:
        """Update occupancy state based on time of day."""
        now = self.clock.now()
        current_time = now.time()
        is_weekday = now.weekday() < 5
        is_wfh_day = random.random() < self.wfh_ratio

        # Determine sleep state
        if current_time >= self.sleep_time or current_time < self.wake_time:
            self.is_sleeping = True
            self.active_areas = ["bedroom"]
        else:
            self.is_sleeping = False

        # Determine home presence
        if is_weekday and not is_wfh_day:
            # Regular work day
            if self.leave_home_time <= current_time < self.return_home_time:
                self.is_home = False
                self.active_areas = []
            else:
                self.is_home = True
        else:
            # Weekend or WFH
            self.is_home = True

        # Determine active areas when home and awake
        if self.is_home and not self.is_sleeping:
            self._update_active_areas()

        # Propagate to entities
        self._update_motion_sensors()
        self._update_person_entities()

    def _update_active_areas(self) -> None:
        """Update which areas of the home are currently active."""
        now = self.clock.now()
        current_time = now.time()

        # Reset active areas
        self.active_areas = []

        # Time-based area activity
        if time(6, 0) <= current_time < time(9, 0):
            # Morning - kitchen, bathroom
            self.active_areas = ["kitchen", "bathroom"]
            if random.random() < 0.3:
                self.active_areas.append("bedroom")

        elif time(9, 0) <= current_time < time(12, 0):
            # Morning/midday
            areas = ["living_room", "kitchen", "office"]
            self.active_areas = [areas[random.randint(0, len(areas)-1)]]

        elif time(12, 0) <= current_time < time(13, 0):
            # Lunch
            self.active_areas = ["kitchen", "dining_room"]

        elif time(13, 0) <= current_time < time(17, 0):
            # Afternoon
            if self.wfh_ratio > 0.5:
                self.active_areas = ["office"]
            else:
                self.active_areas = ["living_room"]

        elif time(17, 0) <= current_time < time(20, 0):
            # Evening - dinner & activities
            self.active_areas = ["kitchen", "living_room"]
            if self.has_kids:
                self.active_areas.append("playroom")

        elif time(20, 0) <= current_time < time(22, 30):
            # Late evening - winding down
            self.active_areas = ["living_room", "bedroom", "bathroom"]

        # Random movement between areas
        if random.random() < 0.2:
            all_areas = ["living_room", "kitchen", "bedroom", "bathroom", "hallway"]
            if random.random() < 0.5 and all_areas:
                self.active_areas.append(random.choice(all_areas))

    def _update_motion_sensors(self) -> None:
        """Update motion sensor states based on occupancy."""
        # Get all motion sensors for this home
        all_states = self.state_manager.get_all_states()

        for state in all_states:
            if state.entity_id.startswith(f"binary_sensor.{self.home_id}_motion"):
                # Extract area from entity ID (if encoded)
                # For now, just use active state
                area = state.attributes.get("area", "unknown")

                should_be_on = (
                    self.is_home and
                    not self.is_sleeping and
                    (area in self.active_areas or random.random() < 0.1)
                )

                new_state = "on" if should_be_on else "off"
                if state.state != new_state:
                    self.state_manager.set_state(
                        state.entity_id,
                        new_state,
                        state.attributes,
                    )

    def _update_person_entities(self) -> None:
        """Update person entity states."""
        # Get person entities for this home
        all_states = self.state_manager.get_all_states()

        for state in all_states:
            if state.entity_id.startswith(f"person.{self.home_id}"):
                new_state = "home" if self.is_home else "away"
                attrs = dict(state.attributes)
                attrs["source"] = "device_tracker"

                if new_state != state.state:
                    self.state_manager.set_state(
                        state.entity_id,
                        new_state,
                        attrs,
                    )

    def set_vacation_mode(self, enabled: bool) -> None:
        """Enable or disable vacation mode.

        Args:
            enabled: Whether vacation mode is enabled
        """
        if enabled:
            self.is_home = False
            self.is_sleeping = False
            self.active_areas = []
        else:
            self.is_home = True
