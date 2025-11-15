# homeiq-sim

**Full-featured Home Assistant Simulator** with real-time API, realistic behaviors, profiles, regions, and seasonality for HomeIQ data collection and testing.

## 🌟 Overview

homeiq-sim is a comprehensive Home Assistant simulator that provides:

- **Home Assistant Compatible APIs** - Full REST and WebSocket APIs compatible with HA clients
- **Real-time Simulation** - Continuous entity state updates with configurable time acceleration
- **Realistic Behaviors** - State machines for lights, climate, sensors, and more
- **Occupancy Patterns** - Simulates daily routines, work-from-home, sleep cycles
- **Weather Integration** - Temperature, humidity, and seasonal effects
- **Multiple Profiles** - Starter, Intermediate, Advanced, and Power user setups
- **Regional Support** - North, South, Arid West, Marine West, East-Midwest multipliers

## 🚀 Quick Start

### Installation

```bash
# Clone and install
git clone <repository>
cd homeiq-sim
uv pip install -e .

# Or with pip
pip install -e .
```

### Running the Simulator

```bash
# Start with default demo home
homeiqsim-serve

# Start with custom configuration
homeiqsim-serve --config examples/config.full.yaml

# Start with 10x time acceleration
homeiqsim-serve --speed 10.0

# Start at a specific date
homeiqsim-serve --start-time "2025-06-01T00:00:00Z"

# Specify host and port
homeiqsim-serve --host 0.0.0.0 --port 8123
```

The simulator will start on http://localhost:8123 by default.

### API Endpoints

Once running, the simulator provides:

- **REST API**: `http://localhost:8123/api/`
- **WebSocket API**: `ws://localhost:8123/api/websocket`
- **API Documentation**: `http://localhost:8123/docs`
- **Health Check**: `http://localhost:8123/health`

### Example API Usage

```bash
# Get all entity states
curl http://localhost:8123/api/states

# Get specific entity
curl http://localhost:8123/api/states/light.demo_home_light_0

# Turn on a light
curl -X POST http://localhost:8123/api/services/light/turn_on \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.demo_home_light_0", "brightness": 255}'

# Get configuration
curl http://localhost:8123/api/config

# Check simulator clock
curl http://localhost:8123/api/simulator/clock
```

## 📦 Features

### Supported Domains

The simulator includes realistic behavior engines for:

#### Core Domains
- **light** - Brightness, color temperature, RGB, effects
- **switch** - Binary on/off with power monitoring
- **binary_sensor** - Motion, door/window, occupancy
- **sensor** - Temperature, humidity, power, energy, battery, illuminance, PM2.5, CO2
- **climate** - Thermostats with heating/cooling, presets, fan modes

#### Additional Domains
- **cover** - Blinds, shades, garage doors with position control
- **media_player** - Playing, paused, volume, source selection

### Real-time Simulation

- **Event Loop** - Scheduled tasks and continuous entity updates
- **Time Acceleration** - Run simulations faster than real-time (1x, 10x, 100x, etc.)
- **Pausable** - Pause and resume simulation
- **Time Travel** - Jump to specific dates

### Realistic Behaviors

- **Occupancy Patterns** - Wake/sleep cycles, work schedules, weekday vs. weekend
- **Motion Detection** - Motion sensors trigger based on occupancy
- **Climate Control** - Thermostats heat/cool to reach setpoint
- **Light Automation** - Lights follow time-of-day patterns
- **Weather Effects** - Temperature sensors follow outdoor weather
- **Energy Monitoring** - Power consumption based on device states

### Home Assistant Compatibility

Full compatibility with Home Assistant clients:

- **REST API** - All standard HA REST endpoints
- **WebSocket API** - Real-time state updates and service calls
- **Service Calls** - Support for turn_on, turn_off, set_temperature, etc.
- **Event Streaming** - Server-sent events for state changes
- **History API** - Access to historical states

## 📁 Configuration

### Configuration File

Create a YAML configuration file:

```yaml
seed: 42
year: 2025

homes:
  counts:
    starter: 25        # Small homes with ~50-320 entities
    intermediate: 45   # Medium homes with ~540-820 entities
    advanced: 23       # Large homes with ~960-1300 entities
    power: 7           # Power user homes with ~1600-2300 entities

  region_mix:
    north: 0.22
    south: 0.24
    arid_west: 0.18
    marine_west: 0.16
    east_midwest: 0.20

feature_probs:
  frigate: 0.45          # Frigate camera integration
  solar: 0.35            # Solar panel integration
  irrigation: 0.40       # Irrigation system
  energy_monitoring: 0.50 # Energy monitoring

occupancy_profiles:
  wfh_ratio: [0.2, 0.5]  # Work from home ratio range
  has_kids_probability: 0.55
  shift_worker_probability: 0.08

seasonality:
  holiday_lights_probability: 0.6
  vacation_weeks_per_home: [1, 3]
  dst_observed: true

output:
  format: parquet
  path: "out/2025/"
  shards_per_month: 8
```

### Profiles

The simulator includes four preconfigured profiles:

| Profile | Entities | Devices | Description |
|---------|----------|---------|-------------|
| Starter | 50-320 | 10-55 | Basic smart home setup |
| Intermediate | 540-820 | 85-120 | Medium automation level |
| Advanced | 960-1300 | 160-210 | Extensive smart home |
| Power | 1600-2300 | 280-380 | Power user with everything |

## 🔧 Advanced Usage

### Python API

Use the simulator programmatically:

```python
from datetime import datetime, timezone
from homeiqsim.simulator import HomeAssistantSimulator

# Create simulator
sim = HomeAssistantSimulator(
    start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
    speed=10.0  # 10x real-time
)

# Create a home
sim.create_home({
    "home_id": "my_home",
    "totals": {
        "lights": 20,
        "switches": 5,
        "motion_sensors": 4,
        "temperature_sensors": 2,
        "thermostats": 1,
    },
    "features": {
        "energy_monitoring": True,
    },
})

# Start simulation
sim.start()

# Get stats
print(sim.get_stats())

# Control time
sim.clock.set_speed(100.0)  # 100x faster
sim.clock.pause()
sim.clock.resume()

# Access state
state = sim.state_manager.get_state("light.my_home_light_0")
print(state.to_dict())

# Call services
sim.service_registry.call_service(
    "light",
    "turn_on",
    "light.my_home_light_0",
    {"brightness": 200}
)

# Stop
sim.stop()
```

### Custom Entity Creation

```python
# Create individual entities
sim.create_entity("light.kitchen", {
    "name": "Kitchen Light",
    "brightness": True,
    "color_temp": True,
})

sim.create_entity("sensor.outdoor_temp", {
    "name": "Outdoor Temperature",
    "device_class": "temperature",
    "outdoor": True,
})

sim.create_entity("climate.living_room", {
    "name": "Living Room Thermostat",
    "humidity_control": True,
})
```

## 📊 Data Generation (Legacy Mode)

The simulator still supports batch data generation:

```bash
# Generate Parquet files
homeiqsim-generate --config examples/config.full.yaml

# Validate output
homeiqsim-validate --manifest out/2025/manifest.json

# Summarize
homeiqsim-summarize --manifest out/2025/manifest.json
```

### Output Structure

```
out/2025/
├── 01/
│   ├── events_2025_01_00.parquet
│   ├── events_2025_01_01.parquet
│   └── ...
├── 02/
│   └── ...
├── device_registry.json
├── entity_registry.json
├── labels.json
└── manifest.json
```

## 🏗️ Architecture

### Core Components

- **Runtime**
  - `SimulationClock` - Virtual clock with time acceleration
  - `StateManager` - Thread-safe entity state storage
  - `EventLoop` - Task scheduling and execution

- **Behaviors**
  - Domain-specific behavior engines
  - Realistic state machines
  - Service call handlers

- **API**
  - `HARestAPI` - FastAPI-based REST endpoints
  - `HAWebSocketAPI` - WebSocket for real-time updates
  - `ServiceRegistry` - Service discovery and dispatch

- **Simulator**
  - `HomeAssistantSimulator` - Main coordinator
  - Ties all components together

### Data Flow

```
Configuration → Simulator → Behavior Engines → State Manager → API
                     ↓
              Event Loop (scheduled tasks)
                     ↓
              State Changes → WebSocket/REST → Clients
```

## 🧪 Testing & Development

### Run Tests

```bash
# Install dev dependencies
uv pip install ruff pytest mypy

# Run tests
pytest -q

# Lint
ruff check .

# Type check
mypy src/
```

### Development Mode

```bash
# Start with auto-reload
homeiqsim-serve --reload

# This will restart the server when code changes
```

## 🎯 Use Cases

1. **HomeIQ Data Collection** - Generate realistic smart home telemetry for ML training
2. **Integration Testing** - Test HomeIQ against a realistic HA instance
3. **Client Development** - Develop HA clients without a physical setup
4. **Algorithm Testing** - Test automation algorithms at accelerated speeds
5. **Load Testing** - Simulate hundreds of homes for scalability testing

## 📝 Configuration Examples

### Small Test Setup

```yaml
homes:
  counts: { starter: 2, intermediate: 1 }
feature_probs: { energy_monitoring: 1.0 }
```

### Large Scale

```yaml
homes:
  counts:
    starter: 100
    intermediate: 200
    advanced: 80
    power: 20
```

### Time Acceleration

```bash
# Run 1 year of simulation in 1 hour
homeiqsim-serve --speed 8760.0 --start-time "2025-01-01T00:00:00Z"
```

## 🔌 Integration with HomeIQ

The simulator is designed to work seamlessly with HomeIQ:

1. Start the simulator
2. Point HomeIQ data collector to the simulator API
3. Collect realistic telemetry data
4. Use time acceleration to quickly generate historical data

## 📄 License

MIT License - see LICENSE file

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- Additional domain support (vacuum, alarm, camera streaming)
- More realistic behavior patterns
- MQTT integration
- Automation engine
- Enhanced weather effects
- Multi-home federation

## 📚 Documentation

- [API Reference](http://localhost:8123/docs) (when running)
- [Home Assistant API](https://developers.home-assistant.io/docs/api/rest/)
- [WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)

## 🙏 Acknowledgments

Built to support HomeIQ smart home data collection and analysis.
