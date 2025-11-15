"""Main simulator coordinator that ties all components together."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

from .runtime import SimulationClock, StateManager, EventLoop
from .behaviors import (
    LightBehavior,
    SwitchBehavior,
    BinarySensorBehavior,
    SensorBehavior,
    ClimateBehavior,
)
from .api import HARestAPI, HAWebSocketAPI, ServiceRegistry
from .core.weather import WeatherDriver

logger = logging.getLogger(__name__)


class HomeAssistantSimulator:
    """Main coordinator for the Home Assistant simulator."""

    def __init__(
        self,
        start_time: Optional[datetime] = None,
        speed: float = 1.0,
    ):
        """Initialize the simulator.

        Args:
            start_time: Initial simulation time (default: current UTC time)
            speed: Time acceleration factor (default: 1.0 = real-time)
        """
        # Core runtime components
        self.clock = SimulationClock(start_time=start_time, speed=speed)
        self.state_manager = StateManager(max_history=1000)
        self.event_loop = EventLoop(self.clock, self.state_manager)

        # Service registry
        self.service_registry = ServiceRegistry()

        # Weather driver (used by sensors/climate)
        self.weather_driver = WeatherDriver(region="north", rng_seed=42)

        # Behavior engines
        self.light_engine = LightBehavior(
            self.state_manager,
            self.clock,
            self.event_loop,
        )
        self.switch_engine = SwitchBehavior(
            self.state_manager,
            self.clock,
            self.event_loop,
        )
        self.binary_sensor_engine = BinarySensorBehavior(
            self.state_manager,
            self.clock,
            self.event_loop,
        )
        self.sensor_engine = SensorBehavior(
            self.state_manager,
            self.clock,
            self.event_loop,
            weather_driver=self._get_weather,
        )
        self.climate_engine = ClimateBehavior(
            self.state_manager,
            self.clock,
            self.event_loop,
            weather_driver=self._get_weather,
        )

        # Register engines with service registry
        self.service_registry.register_engine(self.light_engine)
        self.service_registry.register_engine(self.switch_engine)
        self.service_registry.register_engine(self.binary_sensor_engine)
        self.service_registry.register_engine(self.sensor_engine)
        self.service_registry.register_engine(self.climate_engine)

        # API components
        self.rest_api = HARestAPI(
            self.state_manager,
            self.clock,
            self.service_registry,
        )
        self.ws_api = HAWebSocketAPI(
            self.state_manager,
            self.clock,
            self.service_registry,
        )

        self._running = False

        logger.info("Home Assistant Simulator initialized")

    def _get_weather(self, timestamp: datetime) -> Dict[str, Any]:
        """Get weather data for a specific timestamp.

        Args:
            timestamp: The timestamp to get weather for

        Returns:
            Weather data dict
        """
        # Get hourly weather
        hour = timestamp.replace(minute=0, second=0, microsecond=0)
        for dt, payload in self.weather_driver.hourly_series(timestamp.year):
            if dt == hour:
                return payload

        # Return default if not found
        return {
            "temp_c": 20.0,
            "rel_humidity": 50.0,
            "precip": 0.0,
        }

    def create_entity(
        self,
        entity_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Create a new entity.

        Args:
            entity_id: The entity ID (e.g., 'light.living_room')
            config: Optional entity configuration

        Returns:
            True if created successfully
        """
        domain = entity_id.split(".")[0]

        # Get the appropriate engine
        engine_map = {
            "light": self.light_engine,
            "switch": self.switch_engine,
            "binary_sensor": self.binary_sensor_engine,
            "sensor": self.sensor_engine,
            "climate": self.climate_engine,
        }

        engine = engine_map.get(domain)
        if not engine:
            logger.warning(f"No engine for domain: {domain}")
            return False

        engine.register_entity(entity_id, config)
        logger.info(f"Created entity: {entity_id}")
        return True

    def create_home(self, home_config: Dict[str, Any]) -> None:
        """Create entities for a simulated home.

        Args:
            home_config: Home configuration dict
        """
        home_id = home_config.get("home_id", "home_001")
        totals = home_config.get("totals", {})
        features = home_config.get("features", {})

        # Create basic entities based on profile
        # Lights
        num_lights = totals.get("lights", 10)
        for i in range(num_lights):
            self.create_entity(
                f"light.{home_id}_light_{i}",
                {
                    "name": f"Light {i}",
                    "brightness": True,
                    "color_temp": i % 3 == 0,  # Every 3rd light has color temp
                    "rgb_color": i % 5 == 0,  # Every 5th light has RGB
                }
            )

        # Switches
        num_switches = totals.get("switches", 5)
        for i in range(num_switches):
            self.create_entity(
                f"switch.{home_id}_switch_{i}",
                {
                    "name": f"Switch {i}",
                    "power_monitoring": i % 2 == 0,  # Half have power monitoring
                    "rated_power": 10.0,
                }
            )

        # Motion sensors
        num_motion = totals.get("motion_sensors", 5)
        for i in range(num_motion):
            self.create_entity(
                f"binary_sensor.{home_id}_motion_{i}",
                {
                    "name": f"Motion Sensor {i}",
                    "device_class": "motion",
                    "battery_powered": True,
                }
            )

        # Temperature sensors
        num_temp = totals.get("temperature_sensors", 3)
        for i in range(num_temp):
            self.create_entity(
                f"sensor.{home_id}_temperature_{i}",
                {
                    "name": f"Temperature Sensor {i}",
                    "device_class": "temperature",
                    "outdoor": i == 0,  # First one is outdoor
                }
            )

        # Humidity sensors
        num_humidity = totals.get("humidity_sensors", 2)
        for i in range(num_humidity):
            self.create_entity(
                f"sensor.{home_id}_humidity_{i}",
                {
                    "name": f"Humidity Sensor {i}",
                    "device_class": "humidity",
                    "outdoor": i == 0,
                }
            )

        # Power sensors (if energy monitoring enabled)
        if features.get("energy_monitoring"):
            self.create_entity(
                f"sensor.{home_id}_power",
                {
                    "name": "Total Power",
                    "device_class": "power",
                }
            )
            self.create_entity(
                f"sensor.{home_id}_energy",
                {
                    "name": "Total Energy",
                    "device_class": "energy",
                    "power_sensor": f"sensor.{home_id}_power",
                }
            )

        # Thermostats
        num_climate = totals.get("thermostats", 1)
        for i in range(num_climate):
            self.create_entity(
                f"climate.{home_id}_thermostat_{i}",
                {
                    "name": f"Thermostat {i}",
                    "humidity_control": i == 0,  # Main thermostat has humidity
                }
            )

        logger.info(f"Created home: {home_id} with {self.state_manager.get_entity_count()} total entities")

    def start(self) -> None:
        """Start the simulator."""
        if self._running:
            logger.warning("Simulator already running")
            return

        logger.info("Starting simulator...")

        # Start all behavior engines
        self.light_engine.start()
        self.switch_engine.start()
        self.binary_sensor_engine.start()
        self.sensor_engine.start()
        self.climate_engine.start()

        # Start event loop
        self.event_loop.start()

        self._running = True
        logger.info("Simulator started")

    def stop(self) -> None:
        """Stop the simulator."""
        if not self._running:
            return

        logger.info("Stopping simulator...")

        # Stop event loop
        self.event_loop.stop()

        # Stop behavior engines
        self.light_engine.stop()
        self.switch_engine.stop()
        self.binary_sensor_engine.stop()
        self.sensor_engine.stop()
        self.climate_engine.stop()

        self._running = False
        logger.info("Simulator stopped")

    def is_running(self) -> bool:
        """Check if simulator is running."""
        return self._running

    def get_api_app(self):
        """Get the FastAPI app for the REST API."""
        return self.rest_api.get_app()

    def get_stats(self) -> Dict[str, Any]:
        """Get simulator statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "running": self._running,
            "entities": self.state_manager.get_entity_count(),
            "domains": self.state_manager.get_domains(),
            "current_time": self.clock.now().isoformat(),
            "speed": self.clock.get_speed(),
            "paused": self.clock.is_paused(),
            "pending_tasks": self.event_loop.get_pending_tasks(),
        }
