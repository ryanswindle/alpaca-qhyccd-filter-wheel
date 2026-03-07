"""
ASCOM Alpaca QHYCCD Filter Wheel Server – Main FastAPI Application

Entrypoint that:
  - Creates the FastAPI application
  - Configures logging (loguru + stdlib intercept)
  - Instantiates FilterWheelDevice instances from config.yaml
  - Starts the Alpaca discovery responder (UDP 32227)
  - Includes management, setup, and filter wheel routers
  - Handles graceful shutdown (disconnects all devices)
"""

from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI

from config import config
from discovery import DiscoveryResponder
import filter_wheel
from filter_wheel_device import FilterWheelDevice
from log import get_logger, setup_logging
import management
import setup


setup_logging()
logger = get_logger()

# Device registry: device_number → FilterWheelDevice
devices: Dict[int, FilterWheelDevice] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager – startup and shutdown."""
    logger.info(f"Starting {config.entity} on {config.server.host}:{config.server.port}")

    # Instantiate devices from config
    for device_config in config.devices:
        dev = FilterWheelDevice(device_config)
        devices[device_config.device_number] = dev
        logger.info(f"Registered device: {device_config.entity}")

    # Share devices dict with routers
    filter_wheel.set_devices(devices)
    management.set_devices(devices)

    # Start Alpaca discovery responder
    try:
        DiscoveryResponder(config.server.host, config.server.port)
    except Exception as e:
        logger.warning(f"Could not start discovery responder: {e}")

    yield

    # Shutdown: disconnect all devices
    for dev in devices.values():
        if dev.connected:
            try:
                dev.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting {config.entity}: {e}")
    logger.info("Server shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="ASCOM Alpaca QHYCCD Filter Wheel Server",
    description="ASCOM Alpaca API for the QHYCCD filter wheel (serial)",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(management.router)
app.include_router(setup.router)
app.include_router(filter_wheel.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
        access_log=False,
    )