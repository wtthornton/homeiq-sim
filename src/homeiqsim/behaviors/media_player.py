"""Media player domain behavior engine."""

from datetime import timedelta
from typing import Any, Dict, Optional
import random

from .base import BehaviorEngine


class MediaPlayerBehavior(BehaviorEngine):
    """Behavior engine for media_player entities."""

    MEDIA_TYPES = ["music", "tvshow", "movie", "video", "podcast"]
    SOURCES = ["Spotify", "YouTube", "Netflix", "Plex", "Apple TV", "HDMI 1", "HDMI 2"]

    def __init__(self, *args, **kwargs):
        super().__init__("media_player", *args, **kwargs)

    def get_initial_state(self, entity_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get initial state for a media player."""
        config = config or {}

        attrs = {
            "friendly_name": config.get("name", entity_id.split(".")[1].replace("_", " ").title()),
            "supported_features": 149563,  # Most features
            "volume_level": 0.3,
            "is_volume_muted": False,
            "source_list": self.SOURCES,
            "source": self.SOURCES[0],
        }

        return {
            "state": "off",
            "attributes": attrs,
        }

    def start(self) -> None:
        """Start media player behavior simulation."""
        self.event_loop.schedule_interval(
            interval=timedelta(minutes=10),
            callback=self._simulate_usage,
            task_id=f"{self.domain}_usage",
        )

    def _simulate_usage(self) -> None:
        """Simulate media player usage based on time of day."""
        current_hour = self.clock.now().hour

        # Usage patterns
        if 6 <= current_hour < 9:  # Morning
            usage_prob = 0.2
        elif 12 <= current_hour < 14:  # Lunch
            usage_prob = 0.15
        elif 17 <= current_hour < 23:  # Evening
            usage_prob = 0.6
        else:  # Night
            usage_prob = 0.05

        for entity_id in self._entities:
            state = self.state_manager.get_state(entity_id)
            if not state:
                continue

            if state.state == "off":
                if random.random() < usage_prob * 0.05:  # Start playing
                    attrs = dict(state.attributes)
                    attrs["media_content_type"] = random.choice(self.MEDIA_TYPES)
                    attrs["media_title"] = f"Sample {attrs['media_content_type'].title()}"
                    attrs["media_artist"] = "Unknown Artist"
                    attrs["media_duration"] = random.randint(180, 7200)
                    attrs["media_position"] = 0
                    attrs["source"] = random.choice(self.SOURCES)
                    self._update_state(entity_id, "playing", attrs)
            elif state.state == "playing":
                # Update position
                attrs = dict(state.attributes)
                pos = attrs.get("media_position", 0)
                dur = attrs.get("media_duration", 300)
                pos += 600  # 10 min interval
                if pos >= dur:
                    # Media ended
                    self._update_state(entity_id, "idle", attrs)
                else:
                    attrs["media_position"] = pos
                    self._update_state(entity_id, "playing", attrs)

                # Random pause/stop
                if random.random() < 0.1:
                    self._update_state(entity_id, "paused", attrs)
                elif random.random() < 0.05:
                    self._update_state(entity_id, "off", attrs)

    def _service_turn_on(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.turn_on service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            self._update_state(entity_id, "idle", state.attributes)

    def _service_turn_off(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.turn_off service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            self._update_state(entity_id, "off", state.attributes)

    def _service_toggle(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.toggle service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            new_state = "off" if state.state in ["playing", "paused", "idle"] else "idle"
            self._update_state(entity_id, new_state, state.attributes)

    def _service_media_play(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.media_play service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            self._update_state(entity_id, "playing", state.attributes)

    def _service_media_pause(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.media_pause service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            self._update_state(entity_id, "paused", state.attributes)

    def _service_media_stop(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.media_stop service."""
        state = self.state_manager.get_state(entity_id)
        if state:
            self._update_state(entity_id, "idle", state.attributes)

    def _service_volume_set(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.volume_set service."""
        volume = data.get("volume_level")
        if volume is not None:
            state = self.state_manager.get_state(entity_id)
            if state:
                attrs = dict(state.attributes)
                attrs["volume_level"] = max(0.0, min(1.0, float(volume)))
                self._update_state(entity_id, state.state, attrs)

    def _service_volume_mute(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.volume_mute service."""
        is_muted = data.get("is_volume_muted")
        if is_muted is not None:
            state = self.state_manager.get_state(entity_id)
            if state:
                attrs = dict(state.attributes)
                attrs["is_volume_muted"] = bool(is_muted)
                self._update_state(entity_id, state.state, attrs)

    def _service_select_source(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Handle media_player.select_source service."""
        source = data.get("source")
        if source:
            state = self.state_manager.get_state(entity_id)
            if state and source in state.attributes.get("source_list", []):
                attrs = dict(state.attributes)
                attrs["source"] = source
                self._update_state(entity_id, state.state, attrs)
