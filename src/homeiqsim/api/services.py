"""Service registry for handling domain service calls."""

from typing import Any, Dict, List, Optional
import logging

from ..behaviors.base import BehaviorEngine

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """Registry and dispatcher for Home Assistant services."""

    def __init__(self):
        """Initialize service registry."""
        self._engines: Dict[str, BehaviorEngine] = {}
        self._services: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def register_engine(self, engine: BehaviorEngine) -> None:
        """Register a behavior engine.

        Args:
            engine: The behavior engine to register
        """
        self._engines[engine.domain] = engine
        logger.info(f"Registered engine for domain: {engine.domain}")

        # Register default services based on domain
        self._register_default_services(engine.domain)

    def _register_default_services(self, domain: str) -> None:
        """Register default services for a domain.

        Args:
            domain: The domain name
        """
        if domain not in self._services:
            self._services[domain] = {}

        # Common services for most domains
        if domain in ["light", "switch", "climate", "fan", "cover", "lock", "media_player"]:
            self._services[domain]["turn_on"] = {
                "description": f"Turn on {domain}",
                "fields": {}
            }
            self._services[domain]["turn_off"] = {
                "description": f"Turn off {domain}",
                "fields": {}
            }
            self._services[domain]["toggle"] = {
                "description": f"Toggle {domain}",
                "fields": {}
            }

        # Domain-specific services
        if domain == "light":
            self._services[domain]["turn_on"]["fields"] = {
                "brightness": {"description": "Brightness (0-255)"},
                "color_temp": {"description": "Color temperature in mireds"},
                "rgb_color": {"description": "RGB color"},
                "effect": {"description": "Light effect"},
            }

        elif domain == "climate":
            self._services[domain]["set_temperature"] = {
                "description": "Set target temperature",
                "fields": {
                    "temperature": {"description": "Target temperature"},
                    "hvac_mode": {"description": "HVAC mode"},
                }
            }
            self._services[domain]["set_hvac_mode"] = {
                "description": "Set HVAC mode",
                "fields": {"hvac_mode": {"description": "HVAC mode"}}
            }
            self._services[domain]["set_preset_mode"] = {
                "description": "Set preset mode",
                "fields": {"preset_mode": {"description": "Preset mode"}}
            }
            self._services[domain]["set_fan_mode"] = {
                "description": "Set fan mode",
                "fields": {"fan_mode": {"description": "Fan mode"}}
            }
            self._services[domain]["set_humidity"] = {
                "description": "Set target humidity",
                "fields": {"humidity": {"description": "Target humidity"}}
            }

        elif domain == "cover":
            self._services[domain]["open_cover"] = {
                "description": "Open cover",
                "fields": {}
            }
            self._services[domain]["close_cover"] = {
                "description": "Close cover",
                "fields": {}
            }
            self._services[domain]["stop_cover"] = {
                "description": "Stop cover",
                "fields": {}
            }
            self._services[domain]["set_cover_position"] = {
                "description": "Set cover position",
                "fields": {"position": {"description": "Position (0-100)"}}
            }

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Call a service.

        Args:
            domain: Service domain
            service: Service name
            entity_id: Target entity ID (optional)
            data: Service data

        Returns:
            True if service was handled, False otherwise
        """
        data = data or {}

        # Get the engine for this domain
        engine = self._engines.get(domain)
        if not engine:
            logger.warning(f"No engine registered for domain: {domain}")
            return False

        # If no entity_id provided, try to get from data
        if not entity_id:
            entity_id = data.get("entity_id")

        if not entity_id:
            logger.warning(f"No entity_id provided for service {domain}.{service}")
            return False

        # Handle list of entity IDs
        if isinstance(entity_id, list):
            results = []
            for eid in entity_id:
                result = engine.handle_service_call(service, eid, data)
                results.append(result)
            return all(results)
        else:
            return engine.handle_service_call(service, entity_id, data)

    def get_services_schema(self) -> Dict[str, Dict[str, Any]]:
        """Get schema of all available services.

        Returns:
            Dictionary of domain -> services
        """
        return self._services

    def get_domain_services(self, domain: str) -> Dict[str, Any]:
        """Get services for a specific domain.

        Args:
            domain: The domain name

        Returns:
            Dictionary of services
        """
        return self._services.get(domain, {})

    def register_custom_service(
        self,
        domain: str,
        service: str,
        description: str,
        fields: Dict[str, Any],
    ) -> None:
        """Register a custom service.

        Args:
            domain: Service domain
            service: Service name
            description: Service description
            fields: Service fields schema
        """
        if domain not in self._services:
            self._services[domain] = {}

        self._services[domain][service] = {
            "description": description,
            "fields": fields,
        }

        logger.info(f"Registered custom service: {domain}.{service}")
