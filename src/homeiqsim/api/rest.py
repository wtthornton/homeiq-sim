"""REST API server compatible with Home Assistant API."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import logging

from ..runtime.state import StateManager
from ..runtime.clock import SimulationClock

logger = logging.getLogger(__name__)


# Pydantic models for request/response validation
class ServiceCallData(BaseModel):
    """Service call request data."""
    domain: str
    service: str
    service_data: Optional[Dict[str, Any]] = None
    target: Optional[Dict[str, Any]] = None


class StateUpdateData(BaseModel):
    """State update request data."""
    state: str
    attributes: Optional[Dict[str, Any]] = None


class HARestAPI:
    """Home Assistant compatible REST API."""

    def __init__(
        self,
        state_manager: StateManager,
        clock: SimulationClock,
        service_registry: Optional[Any] = None,
    ):
        """Initialize REST API.

        Args:
            state_manager: State manager instance
            clock: Simulation clock
            service_registry: Service registry for handling service calls
        """
        self.state_manager = state_manager
        self.clock = clock
        self.service_registry = service_registry
        self.app = FastAPI(
            title="HomeIQ Simulator API",
            description="Home Assistant compatible API for HomeIQ simulator",
            version="1.0.0",
        )

        # Setup routes
        self._setup_routes()

        # Event subscribers for SSE
        self._event_subscribers: List[asyncio.Queue] = []

        # Listen to state changes
        self.state_manager.add_listener(self._on_state_change)

    def _setup_routes(self) -> None:
        """Setup all API routes."""

        @self.app.get("/api/")
        async def api_discovery():
            """API discovery endpoint."""
            return {
                "message": "API running.",
                "version": "1.0.0",
            }

        @self.app.get("/api/config")
        async def get_config():
            """Get configuration."""
            return {
                "location_name": "HomeIQ Simulator",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "elevation": 0,
                "unit_system": {
                    "length": "km",
                    "mass": "g",
                    "temperature": "°C",
                    "volume": "L",
                },
                "time_zone": "UTC",
                "components": [
                    "light",
                    "switch",
                    "binary_sensor",
                    "sensor",
                    "climate",
                    "api",
                ],
                "version": "2024.1.0",
                "state": "RUNNING",
            }

        @self.app.get("/api/states")
        async def get_states():
            """Get all entity states."""
            states = self.state_manager.get_all_states()
            return [state.to_dict() for state in states]

        @self.app.get("/api/states/{entity_id}")
        async def get_state(entity_id: str):
            """Get single entity state."""
            state = self.state_manager.get_state(entity_id)
            if not state:
                raise HTTPException(status_code=404, detail="Entity not found")
            return state.to_dict()

        @self.app.post("/api/states/{entity_id}")
        async def set_state(entity_id: str, data: StateUpdateData):
            """Set entity state (for testing/debugging)."""
            new_state = self.state_manager.set_state(
                entity_id,
                data.state,
                data.attributes,
            )
            return new_state.to_dict()

        @self.app.post("/api/services/{domain}/{service}")
        async def call_service(domain: str, service: str, request: Request):
            """Call a service."""
            try:
                data = await request.json() if request.headers.get("content-type") == "application/json" else {}
            except Exception:
                data = {}

            if not self.service_registry:
                raise HTTPException(status_code=501, detail="Service registry not available")

            # Extract entity_id from data or target
            entity_ids = []
            if "entity_id" in data:
                entity_id = data["entity_id"]
                if isinstance(entity_id, list):
                    entity_ids = entity_id
                else:
                    entity_ids = [entity_id]
            elif "target" in data and "entity_id" in data["target"]:
                entity_id = data["target"]["entity_id"]
                if isinstance(entity_id, list):
                    entity_ids = entity_id
                else:
                    entity_ids = [entity_id]

            results = []
            for entity_id in entity_ids:
                success = self.service_registry.call_service(domain, service, entity_id, data)
                results.append({
                    "entity_id": entity_id,
                    "success": success,
                })

            if not entity_ids:
                # Service call without specific entity
                success = self.service_registry.call_service(domain, service, None, data)
                results.append({"success": success})

            return results

        @self.app.get("/api/error_log")
        async def get_error_log():
            """Get error log (stub)."""
            return []

        @self.app.get("/api/events")
        async def event_stream():
            """Server-sent events stream."""
            async def event_generator():
                queue = asyncio.Queue()
                self._event_subscribers.append(queue)

                try:
                    while True:
                        event = await queue.get()
                        yield f"data: {json.dumps(event)}\n\n"
                except asyncio.CancelledError:
                    pass
                finally:
                    if queue in self._event_subscribers:
                        self._event_subscribers.remove(queue)

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
            )

        @self.app.get("/api/history/period")
        async def get_history(
            filter_entity_id: Optional[str] = None,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None,
        ):
            """Get historical states."""
            if filter_entity_id:
                entity_ids = [filter_entity_id]
            else:
                # Return all entities
                entity_ids = [state.entity_id for state in self.state_manager.get_all_states()]

            start_dt = None
            end_dt = None

            if start_time:
                try:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                except Exception:
                    pass

            if end_time:
                try:
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                except Exception:
                    pass

            result = {}
            for entity_id in entity_ids:
                history = self.state_manager.get_history(entity_id, start_dt, end_dt)
                if history:
                    result[entity_id] = [state.to_dict() for state in history]

            return result

        @self.app.get("/api/logbook/{timestamp}")
        async def get_logbook(timestamp: str):
            """Get logbook entries (stub)."""
            return []

        @self.app.get("/api/services")
        async def get_services():
            """Get available services."""
            if not self.service_registry:
                return {}

            return self.service_registry.get_services_schema()

        @self.app.get("/api/camera_proxy/{entity_id}")
        async def camera_proxy(entity_id: str):
            """Camera proxy (stub - returns placeholder)."""
            raise HTTPException(status_code=404, detail="Camera streaming not implemented")

        @self.app.get("/api/core/components")
        async def get_components():
            """Get loaded components."""
            return [
                "light",
                "switch",
                "binary_sensor",
                "sensor",
                "climate",
                "api",
                "websocket_api",
            ]

        @self.app.get("/api/discovery_info")
        async def discovery_info():
            """Discovery information."""
            return {
                "base_url": "http://localhost:8123",
                "external_url": None,
                "internal_url": "http://localhost:8123",
                "location_name": "HomeIQ Simulator",
                "requires_api_password": False,
                "version": "2024.1.0",
            }

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "entities": self.state_manager.get_entity_count(),
                "timestamp": self.clock.now().isoformat(),
            }

        @self.app.get("/api/simulator/clock")
        async def get_clock_info():
            """Get simulation clock information (custom endpoint)."""
            return {
                "current_time": self.clock.now().isoformat(),
                "speed": self.clock.get_speed(),
                "paused": self.clock.is_paused(),
            }

        @self.app.post("/api/simulator/clock/set_time")
        async def set_clock_time(data: Dict[str, Any]):
            """Set simulation time (custom endpoint)."""
            if "time" not in data:
                raise HTTPException(status_code=400, detail="Missing 'time' field")

            try:
                new_time = datetime.fromisoformat(data["time"].replace("Z", "+00:00"))
                self.clock.set_time(new_time)
                return {"success": True, "time": self.clock.now().isoformat()}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/api/simulator/clock/set_speed")
        async def set_clock_speed(data: Dict[str, Any]):
            """Set simulation speed (custom endpoint)."""
            if "speed" not in data:
                raise HTTPException(status_code=400, detail="Missing 'speed' field")

            try:
                speed = float(data["speed"])
                self.clock.set_speed(speed)
                return {"success": True, "speed": self.clock.get_speed()}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/api/simulator/clock/pause")
        async def pause_clock():
            """Pause simulation (custom endpoint)."""
            self.clock.pause()
            return {"success": True, "paused": True}

        @self.app.post("/api/simulator/clock/resume")
        async def resume_clock():
            """Resume simulation (custom endpoint)."""
            self.clock.resume()
            return {"success": True, "paused": False}

    def _on_state_change(self, new_state, old_state):
        """Handle state changes and notify event subscribers."""
        event = {
            "event_type": "state_changed",
            "data": {
                "entity_id": new_state.entity_id,
                "old_state": old_state.to_dict() if old_state else None,
                "new_state": new_state.to_dict(),
            },
            "time_fired": datetime.utcnow().isoformat(),
        }

        # Notify all subscribers (non-blocking)
        for queue in self._event_subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Skip if queue is full

    def get_app(self) -> FastAPI:
        """Get the FastAPI app instance."""
        return self.app
