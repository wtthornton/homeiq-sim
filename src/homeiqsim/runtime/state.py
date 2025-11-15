"""State management system for Home Assistant simulator.

Provides thread-safe storage and retrieval of entity states with history tracking.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Optional
import copy


@dataclass
class EntityState:
    """Represents a single entity state."""
    entity_id: str
    state: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_changed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Convert to HA-compatible dict."""
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self.attributes,
            "last_changed": self.last_changed.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "context": self.context or {"id": "", "parent_id": None, "user_id": None},
        }

    def clone(self) -> "EntityState":
        """Create a deep copy of this state."""
        return EntityState(
            entity_id=self.entity_id,
            state=self.state,
            attributes=copy.deepcopy(self.attributes),
            last_changed=self.last_changed,
            last_updated=self.last_updated,
            context=copy.deepcopy(self.context) if self.context else None,
        )


class StateManager:
    """Thread-safe state manager for all entities in the simulation."""

    def __init__(self, max_history: int = 1000):
        """Initialize state manager.

        Args:
            max_history: Maximum number of historical states to keep per entity
        """
        self._states: Dict[str, EntityState] = {}
        self._history: Dict[str, List[EntityState]] = {}
        self._max_history = max_history
        self._lock = RLock()
        self._listeners: List[callable] = []

    def set_state(
        self,
        entity_id: str,
        state: str,
        attributes: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        force_update: bool = False,
    ) -> EntityState:
        """Set or update an entity's state.

        Args:
            entity_id: The entity ID
            state: The new state value
            attributes: Optional attributes dict
            context: Optional context information
            force_update: If True, always update last_updated even if state unchanged

        Returns:
            The new EntityState object
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            attributes = attributes or {}

            old_state = self._states.get(entity_id)

            # Determine if state actually changed
            state_changed = (
                old_state is None or
                old_state.state != state or
                old_state.attributes != attributes
            )

            new_state = EntityState(
                entity_id=entity_id,
                state=state,
                attributes=attributes,
                last_changed=now if state_changed else (old_state.last_changed if old_state else now),
                last_updated=now,
                context=context,
            )

            # Store old state in history
            if old_state and state_changed:
                if entity_id not in self._history:
                    self._history[entity_id] = []
                self._history[entity_id].append(old_state.clone())
                # Trim history if needed
                if len(self._history[entity_id]) > self._max_history:
                    self._history[entity_id] = self._history[entity_id][-self._max_history:]

            self._states[entity_id] = new_state

            # Notify listeners
            if state_changed or force_update:
                self._notify_listeners(new_state, old_state)

            return new_state

    def get_state(self, entity_id: str) -> Optional[EntityState]:
        """Get current state of an entity.

        Args:
            entity_id: The entity ID

        Returns:
            EntityState or None if not found
        """
        with self._lock:
            state = self._states.get(entity_id)
            return state.clone() if state else None

    def get_all_states(self) -> List[EntityState]:
        """Get all entity states.

        Returns:
            List of all EntityState objects
        """
        with self._lock:
            return [state.clone() for state in self._states.values()]

    def get_states_by_domain(self, domain: str) -> List[EntityState]:
        """Get all states for entities in a domain.

        Args:
            domain: The domain (e.g., 'light', 'sensor')

        Returns:
            List of EntityState objects
        """
        with self._lock:
            return [
                state.clone()
                for entity_id, state in self._states.items()
                if entity_id.split(".")[0] == domain
            ]

    def get_history(
        self,
        entity_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[EntityState]:
        """Get historical states for an entity.

        Args:
            entity_id: The entity ID
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of historical EntityState objects
        """
        with self._lock:
            history = self._history.get(entity_id, [])

            if start_time or end_time:
                filtered = []
                for state in history:
                    if start_time and state.last_updated < start_time:
                        continue
                    if end_time and state.last_updated > end_time:
                        continue
                    filtered.append(state.clone())
                return filtered

            return [state.clone() for state in history]

    def remove_state(self, entity_id: str) -> bool:
        """Remove an entity's state.

        Args:
            entity_id: The entity ID

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if entity_id in self._states:
                del self._states[entity_id]
                if entity_id in self._history:
                    del self._history[entity_id]
                return True
            return False

    def add_listener(self, callback: callable) -> None:
        """Add a state change listener.

        Args:
            callback: Function to call on state changes, signature:
                     callback(new_state: EntityState, old_state: Optional[EntityState])
        """
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: callable) -> bool:
        """Remove a state change listener.

        Args:
            callback: The callback to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)
                return True
            return False

    def _notify_listeners(self, new_state: EntityState, old_state: Optional[EntityState]) -> None:
        """Notify all listeners of a state change."""
        for listener in self._listeners:
            try:
                listener(new_state.clone(), old_state.clone() if old_state else None)
            except Exception as e:
                # Log but don't fail on listener errors
                print(f"Error in state listener: {e}")

    def clear(self) -> None:
        """Clear all states and history."""
        with self._lock:
            self._states.clear()
            self._history.clear()

    def get_entity_count(self) -> int:
        """Get total number of entities."""
        with self._lock:
            return len(self._states)

    def get_domains(self) -> List[str]:
        """Get list of all domains with entities."""
        with self._lock:
            domains = set()
            for entity_id in self._states.keys():
                domain = entity_id.split(".")[0]
                domains.add(domain)
            return sorted(domains)
