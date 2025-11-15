"""WebSocket API compatible with Home Assistant."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum

from ..runtime.state import StateManager, EntityState
from ..runtime.clock import SimulationClock

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    AUTH = "auth"
    AUTH_REQUIRED = "auth_required"
    AUTH_OK = "auth_ok"
    AUTH_INVALID = "auth_invalid"
    RESULT = "result"
    EVENT = "event"
    PONG = "pong"


class WSClient:
    """Represents a connected WebSocket client."""

    def __init__(self, websocket: WebSocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.authenticated = False
        self.subscriptions: Dict[int, str] = {}  # subscription_id -> event_type
        self.state_subscriptions: Set[str] = set()  # entity_ids for state subscriptions
        self.message_id = 0


class HAWebSocketAPI:
    """Home Assistant compatible WebSocket API."""

    def __init__(
        self,
        state_manager: StateManager,
        clock: SimulationClock,
        service_registry: Optional[Any] = None,
    ):
        """Initialize WebSocket API.

        Args:
            state_manager: State manager instance
            clock: Simulation clock
            service_registry: Service registry for handling service calls
        """
        self.state_manager = state_manager
        self.clock = clock
        self.service_registry = service_registry
        self._clients: List[WSClient] = []
        self._client_counter = 0

        # Listen to state changes
        self.state_manager.add_listener(self._on_state_change)

    async def handle_connection(self, websocket: WebSocket) -> None:
        """Handle a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
        """
        await websocket.accept()
        self._client_counter += 1
        client = WSClient(websocket, f"client_{self._client_counter}")
        self._clients.append(client)

        try:
            # Send auth required
            await self._send_message(
                client,
                {
                    "type": MessageType.AUTH_REQUIRED,
                    "ha_version": "2024.1.0",
                }
            )

            # Handle messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self._handle_message(client, message)
                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client {client.client_id}")
                except Exception as e:
                    logger.error(f"Error handling message from {client.client_id}: {e}")

        finally:
            # Cleanup
            if client in self._clients:
                self._clients.remove(client)
            logger.info(f"Client {client.client_id} disconnected")

    async def _handle_message(self, client: WSClient, message: Dict[str, Any]) -> None:
        """Handle an incoming WebSocket message.

        Args:
            client: The client that sent the message
            message: The message data
        """
        msg_type = message.get("type")
        msg_id = message.get("id")

        if msg_type == MessageType.AUTH:
            # Simple auth - accept any token for simulation
            client.authenticated = True
            await self._send_message(client, {"type": MessageType.AUTH_OK, "ha_version": "2024.1.0"})
            logger.info(f"Client {client.client_id} authenticated")

        elif not client.authenticated:
            await self._send_message(client, {"type": MessageType.AUTH_INVALID, "message": "Authentication required"})

        elif msg_type == "ping":
            await self._send_message(client, {"id": msg_id, "type": MessageType.PONG})

        elif msg_type == "get_states":
            states = self.state_manager.get_all_states()
            await self._send_result(client, msg_id, [state.to_dict() for state in states])

        elif msg_type == "get_config":
            await self._send_result(client, msg_id, {
                "location_name": "HomeIQ Simulator",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "unit_system": {"temperature": "°C"},
                "time_zone": "UTC",
                "version": "2024.1.0",
            })

        elif msg_type == "get_services":
            if self.service_registry:
                services = self.service_registry.get_services_schema()
                await self._send_result(client, msg_id, services)
            else:
                await self._send_result(client, msg_id, {})

        elif msg_type == "subscribe_events":
            event_type = message.get("event_type")
            if event_type:
                client.subscriptions[msg_id] = event_type
                await self._send_result(client, msg_id, {"success": True})
                logger.debug(f"Client {client.client_id} subscribed to {event_type}")
            else:
                await self._send_error(client, msg_id, "missing_event_type", "Event type required")

        elif msg_type == "unsubscribe_events":
            subscription_id = message.get("subscription")
            if subscription_id in client.subscriptions:
                del client.subscriptions[subscription_id]
                await self._send_result(client, msg_id, {"success": True})
            else:
                await self._send_error(client, msg_id, "not_found", "Subscription not found")

        elif msg_type == "call_service":
            domain = message.get("domain")
            service = message.get("service")
            service_data = message.get("service_data", {})
            target = message.get("target", {})

            if not domain or not service:
                await self._send_error(client, msg_id, "missing_data", "Domain and service required")
                return

            if not self.service_registry:
                await self._send_error(client, msg_id, "not_supported", "Service registry not available")
                return

            # Extract entity IDs
            entity_ids = []
            if "entity_id" in target:
                entity_id = target["entity_id"]
                entity_ids = entity_id if isinstance(entity_id, list) else [entity_id]
            elif "entity_id" in service_data:
                entity_id = service_data["entity_id"]
                entity_ids = entity_id if isinstance(entity_id, list) else [entity_id]

            results = []
            for entity_id in entity_ids or [None]:
                success = self.service_registry.call_service(domain, service, entity_id, service_data)
                results.append({"entity_id": entity_id, "success": success})

            await self._send_result(client, msg_id, {"context": {"id": "simulated"}})

        elif msg_type == "subscribe_trigger":
            # Trigger subscriptions (simplified)
            await self._send_result(client, msg_id, {"success": True})

        elif msg_type == "render_template":
            # Template rendering (stub)
            template = message.get("template", "")
            await self._send_result(client, msg_id, template)

        else:
            logger.warning(f"Unknown message type: {msg_type}")
            await self._send_error(client, msg_id, "unknown_command", f"Unknown command: {msg_type}")

    async def _send_message(self, client: WSClient, message: Dict[str, Any]) -> None:
        """Send a message to a client.

        Args:
            client: The client to send to
            message: The message data
        """
        try:
            await client.websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to {client.client_id}: {e}")

    async def _send_result(self, client: WSClient, msg_id: int, result: Any) -> None:
        """Send a result message.

        Args:
            client: The client to send to
            msg_id: The message ID this is responding to
            result: The result data
        """
        await self._send_message(client, {
            "id": msg_id,
            "type": MessageType.RESULT,
            "success": True,
            "result": result,
        })

    async def _send_error(
        self,
        client: WSClient,
        msg_id: int,
        code: str,
        message: str
    ) -> None:
        """Send an error message.

        Args:
            client: The client to send to
            msg_id: The message ID this is responding to
            code: Error code
            message: Error message
        """
        await self._send_message(client, {
            "id": msg_id,
            "type": MessageType.RESULT,
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        })

    def _on_state_change(self, new_state: EntityState, old_state: Optional[EntityState]) -> None:
        """Handle state changes and notify subscribed clients.

        Args:
            new_state: The new state
            old_state: The previous state
        """
        event = {
            "event_type": "state_changed",
            "data": {
                "entity_id": new_state.entity_id,
                "old_state": old_state.to_dict() if old_state else None,
                "new_state": new_state.to_dict(),
            },
            "origin": "LOCAL",
            "time_fired": datetime.utcnow().isoformat(),
        }

        # Send to all subscribed clients
        for client in self._clients:
            if not client.authenticated:
                continue

            # Check subscriptions
            for sub_id, event_type in client.subscriptions.items():
                if event_type == "state_changed" or event_type == "*":
                    # Send event
                    asyncio.create_task(
                        self._send_message(client, {
                            "id": sub_id,
                            "type": MessageType.EVENT,
                            "event": event,
                        })
                    )

    def broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast a custom event to all subscribed clients.

        Args:
            event_type: The event type
            data: Event data
        """
        event = {
            "event_type": event_type,
            "data": data,
            "origin": "LOCAL",
            "time_fired": datetime.utcnow().isoformat(),
        }

        for client in self._clients:
            if not client.authenticated:
                continue

            for sub_id, subscribed_type in client.subscriptions.items():
                if subscribed_type == event_type or subscribed_type == "*":
                    asyncio.create_task(
                        self._send_message(client, {
                            "id": sub_id,
                            "type": MessageType.EVENT,
                            "event": event,
                        })
                    )
