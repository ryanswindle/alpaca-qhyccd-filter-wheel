from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


def _load_yaml_configs() -> dict:
    """Load config.yaml with optional docker override."""

    base_config = {}
    override_config = {}

    base_path = Path(__file__).parent / "config.yaml"
    if base_path.exists():
        with open(base_path, "r") as f:
            base_config = yaml.safe_load(f) or {}

    docker_path = Path("/alpyca/config.yaml")
    if docker_path.exists():
        with open(docker_path, "r") as f:
            override_config = yaml.safe_load(f) or {}

    def deep_merge(base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    return deep_merge(base_config, override_config)


class DeviceConfig(BaseModel):
    """Configuration for a single QHYCCD filter wheel."""

    entity: str = Field(default="Filter Wheel")
    device_number: int = Field(default=0)
    serial_port: str = Field(default="/dev/ttyUSB1")
    names: List[str] = Field(
        default_factory=lambda: ["Filter 1", "Filter 2", "Filter 3", "Filter 4", "Filter 5", "Filter 6", "Filter 7"]
    )
    focus_offsets: List[int] = Field(
        default_factory=lambda: [0, 0, 0, 0, 0, 0, 0]
    )
    timeout: int = Field(default=60)


class ServerConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=5000)


class Config(BaseModel):
    entity: str = Field(default="qhycfw")
    server: ServerConfig = Field(default_factory=ServerConfig)
    log_level: str = Field(default="INFO")
    devices: List[DeviceConfig] = Field(default_factory=list)

    @classmethod
    def load(cls) -> "Config":
        return cls(**_load_yaml_configs())

    def get_device(self, device_number: int) -> Optional[DeviceConfig]:
        for device in self.devices:
            if device.device_number == device_number:
                return device
        return None


config = Config.load()
