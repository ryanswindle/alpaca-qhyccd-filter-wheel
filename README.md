# QHYCCD – ASCOM Alpaca Server for QHYCCD Filter Wheel (Serial)

A FastAPI-based server, implementing the **IFilterWheelV3** interface. Communication is via serial protocol (9600 8N1).ser

---

## Implemented IFilterWheelV3 capabilities as of this driver version

| Property/Method | Supported |
|-----------------|-----------|
| FocusOffsets    | ✔         |
| Names           | ✔         |
| Position        | ✔         |

Tested on the CFW3XL, which is a 7-position filter wheel. The wheel homes automatically on power and onconnect.

---

## Architecture

| File                    | Purpose                                     |
|-------------------------|---------------------------------------------|
| `main.py`               | FastAPI app, lifespan, router wiring        |
| `config.py`             | Pydantic config models, YAML loader         |
| `config.yaml`           | User-editable configuration                 |
| `filter.py`             | FastAPI router – IFilterWheelV3 endpoints   |
| `filter_wheel_device.py`| Low-level serial driver                     |
| `management.py`         | `/management` Alpaca management endpoints   |
| `setup.py`              | `/setup` HTML stub pages                    |
| `discovery.py`          | UDP Alpaca discovery responder (port 32227) |
| `responses.py`          | Pydantic response models                    |
| `exceptions.py`         | ASCOM Alpaca error classes                  |
| `shr.py`                | Shared FastAPI dependencies / helpers       |
| `log.py`                | Loguru config + stdlib intercept handler    |
| `test.py`               | Quick smoke-test script                     |
| `requirements.txt`      | Python package dependencies                 |
| `Dockerfile`            | Container build                             |

---

## Serial protocol notes

The CFW3XL uses a simple ASCII protocol at 9600 baud, 8N1:

- **Position query** — send `NOW`, read 1 byte (`'0'`–`'6'`).
- **Position command** — send a single ASCII digit (`'0'`–`'6'`).
- **Homing** — the wheel homes to position 0 automatically when the
  wheel is powered on and upon connecting.
- **No "moving" flag** — the driver polls position in a background
  thread until the target is reached or a timeout occurs.

---

## Configuration

Edit `config.yaml` to match your filter wheel setup.

Multiple QHYCCD filter wheels can be registered by adding further entries under
`devices:` with distinct `device_number` values.

---

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

The server starts on `0.0.0.0:5000` by default (configurable in `config.yaml`).

---

## Smoke test

```bash
# Requires hardware connected – will cycle through all filter positions
python test.py
```

---

## Docker

```bash
docker build -t alpaca-qhyccd-filter-wheel .
docker run -d --name alpaca-qhyccd-filter-wheel \
    -v ./config.yaml:/alpyca/config.yaml:ro \
    --network host \
    --device /dev/ttyUSB1 \
    --restart unless-stopped \
    alpaca-qhyccd-filter-wheel
docker logs -f alpaca-qhyccd-filter-wheel
```