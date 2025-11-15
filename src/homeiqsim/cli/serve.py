"""CLI command to start the Home Assistant simulator server."""

from datetime import datetime, timezone
from pathlib import Path
import logging
import click
import uvicorn
import yaml
from fastapi import FastAPI

from ..simulator import HomeAssistantSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Configuration file path",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind to (default: 0.0.0.0)",
)
@click.option(
    "--port",
    default=8123,
    type=int,
    help="Port to bind to (default: 8123)",
)
@click.option(
    "--speed",
    default=1.0,
    type=float,
    help="Time acceleration factor (default: 1.0 = real-time)",
)
@click.option(
    "--start-time",
    type=str,
    help="Initial simulation time (ISO format, default: current time)",
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload on code changes",
)
def main(config, host, port, speed, start_time, reload):
    """Start the Home Assistant simulator server.

    This starts a full Home Assistant compatible API server with REST and WebSocket
    endpoints. The simulator will generate realistic entity behaviors in real-time.

    Examples:
        # Start with default settings
        homeiqsim-serve

        # Start with 10x time acceleration
        homeiqsim-serve --speed 10.0

        # Start at a specific date
        homeiqsim-serve --start-time "2025-01-01T00:00:00Z"

        # Load configuration file
        homeiqsim-serve --config examples/config.full.yaml
    """
    click.echo("╔═══════════════════════════════════════════════════════╗")
    click.echo("║   HomeIQ Simulator - Home Assistant Compatible API   ║")
    click.echo("╚═══════════════════════════════════════════════════════╝")
    click.echo()

    # Parse start time
    start_dt = None
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            click.echo(f"📅 Start time: {start_dt.isoformat()}")
        except Exception as e:
            click.echo(f"❌ Error parsing start time: {e}", err=True)
            return

    # Initialize simulator
    click.echo(f"⚡ Speed: {speed}x")
    simulator = HomeAssistantSimulator(start_time=start_dt, speed=speed)

    # Load configuration if provided
    if config:
        click.echo(f"📄 Loading configuration from: {config}")
        try:
            cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))

            # Create homes based on config
            homes_cfg = cfg.get("homes", {})
            counts = homes_cfg.get("counts", {})
            features = cfg.get("feature_probs", {})

            total_homes = sum(counts.values())
            click.echo(f"🏠 Creating {total_homes} homes...")

            for profile, count in counts.items():
                for i in range(count):
                    home_config = {
                        "home_id": f"{profile}_{i:03d}",
                        "profile": profile,
                        "totals": {
                            "lights": 10 if profile == "starter" else 20 if profile == "intermediate" else 30,
                            "switches": 3 if profile == "starter" else 5 if profile == "intermediate" else 8,
                            "motion_sensors": 2 if profile == "starter" else 4 if profile == "intermediate" else 6,
                            "temperature_sensors": 1 if profile == "starter" else 2 if profile == "intermediate" else 3,
                            "humidity_sensors": 1,
                            "thermostats": 1 if profile in ["starter", "intermediate"] else 2,
                        },
                        "features": {
                            "frigate": False,
                            "solar": False,
                            "irrigation": False,
                            "energy_monitoring": True,
                        },
                    }
                    simulator.create_home(home_config)

        except Exception as e:
            click.echo(f"❌ Error loading configuration: {e}", err=True)
            logger.exception("Configuration error")
            return
    else:
        # Create a default demo home
        click.echo("🏠 Creating demo home...")
        simulator.create_home({
            "home_id": "demo_home",
            "totals": {
                "lights": 15,
                "switches": 5,
                "motion_sensors": 4,
                "temperature_sensors": 2,
                "humidity_sensors": 1,
                "thermostats": 1,
            },
            "features": {
                "energy_monitoring": True,
            },
        })

    # Get stats
    stats = simulator.get_stats()
    click.echo(f"✅ Initialized {stats['entities']} entities across {len(stats['domains'])} domains")
    click.echo(f"📊 Domains: {', '.join(stats['domains'])}")
    click.echo()

    # Start simulator
    click.echo("🚀 Starting simulator...")
    simulator.start()

    # Get FastAPI app
    app = simulator.get_api_app()

    # Add WebSocket endpoint
    @app.websocket("/api/websocket")
    async def websocket_endpoint(websocket):
        await simulator.ws_api.handle_connection(websocket)

    # Start server
    click.echo(f"🌐 Starting API server on http://{host}:{port}")
    click.echo()
    click.echo("📍 API Endpoints:")
    click.echo(f"   • REST API:      http://{host}:{port}/api/")
    click.echo(f"   • WebSocket:     ws://{host}:{port}/api/websocket")
    click.echo(f"   • Health Check:  http://{host}:{port}/health")
    click.echo(f"   • API Docs:      http://{host}:{port}/docs")
    click.echo()
    click.echo("Press Ctrl+C to stop...")
    click.echo()

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            reload=reload,
        )
    except KeyboardInterrupt:
        click.echo("\n🛑 Shutting down...")
    finally:
        simulator.stop()
        click.echo("✅ Simulator stopped")


if __name__ == "__main__":
    main()
