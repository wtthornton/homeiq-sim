"""Base behavior engine for entity simulation."""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set
import logging

from ..runtime.state import StateManager
from ..runtime.clock import SimulationClock
from ..runtime.loop import EventLoop

logger = logging.getLogger(__name__)


class BehaviorEngine(ABC):
    """Base class for domain-specific behavior engines."""

    def __init__(
        self,
        domain: str,
        state_manager: StateManager,
        clock: SimulationClock,
        event_loop: EventLoop,
    ):
        """Initialize behavior engine.

        Args:
            domain: The domain this engine handles (e.g., 'light', 'sensor')
            state_manager: State manager instance
            clock: Simulation clock
            event_loop: Event loop for scheduling
        """
        self.domain = domain
        self.state_manager = state_manager
        self.clock = clock
        self.event_loop = event_loop
        self._entities: Set[str] = set()
        self._entity_config: Dict[str, Dict[str, Any]] = {}

    def register_entity(self, entity_id: str, config: Optional[Dict[str, Any]] = None) -> None:
        """Register an entity with this behavior engine.

        Args:
            entity_id: The entity ID
            config: Optional configuration for the entity
        """
        if not entity_id.startswith(f"{self.domain}."):
            logger.warning(f"Entity {entity_id} doesn't match domain {self.domain}")
            return

        self._entities.add(entity_id)
        if config:
            self._entity_config[entity_id] = config

        # Initialize entity state if needed
        if not self.state_manager.get_state(entity_id):
            initial_state = self.get_initial_state(entity_id, config)
            self.state_manager.set_state(
                entity_id,
                initial_state["state"],
                initial_state.get("attributes", {}),
            )

        logger.debug(f"Registered {entity_id} with {self.domain} engine")

    def unregister_entity(self, entity_id: str) -> None:
        """Unregister an entity.

        Args:
            entity_id: The entity ID
        """
        self._entities.discard(entity_id)
        self._entity_config.pop(entity_id, None)

    def get_entities(self) -> List[str]:
        """Get all registered entities."""
        return list(self._entities)

    def get_entity_config(self, entity_id: str) -> Dict[str, Any]:
        """Get configuration for an entity."""
        return self._entity_config.get(entity_id, {})

    @abstractmethod
    def get_initial_state(self, entity_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get initial state for an entity.

        Args:
            entity_id: The entity ID
            config: Optional configuration

        Returns:
            Dict with 'state' and optionally 'attributes'
        """
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the behavior engine.

        This should schedule any recurring tasks or initial behaviors.
        """
        pass

    def stop(self) -> None:
        """Stop the behavior engine.

        Override to clean up any scheduled tasks.
        """
        pass

    def handle_service_call(
        self,
        service: str,
        entity_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Handle a service call for this domain.

        Args:
            service: Service name (e.g., 'turn_on', 'turn_off')
            entity_id: Target entity ID
            data: Optional service data

        Returns:
            True if handled, False otherwise
        """
        if entity_id not in self._entities:
            return False

        method_name = f"_service_{service}"
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            try:
                method(entity_id, data or {})
                return True
            except Exception as e:
                logger.error(f"Error handling service {service} for {entity_id}: {e}")
                return False

        logger.warning(f"Unhandled service: {self.domain}.{service}")
        return False

    def _update_state(
        self,
        entity_id: str,
        state: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Helper to update entity state.

        Args:
            entity_id: The entity ID
            state: New state value
            attributes: Optional attributes to update/add
        """
        current = self.state_manager.get_state(entity_id)
        if current:
            # Merge attributes
            new_attrs = dict(current.attributes)
            if attributes:
                new_attrs.update(attributes)
            self.state_manager.set_state(entity_id, state, new_attrs)
        else:
            self.state_manager.set_state(entity_id, state, attributes or {})
