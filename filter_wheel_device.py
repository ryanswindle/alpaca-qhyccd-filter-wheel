from datetime import datetime, timezone
import threading
import time

import serial

from config import DeviceConfig
from log import get_logger


logger = get_logger()


class FilterWheelBusyError(RuntimeError):
    """Raised when a command is rejected because the wheel is currently moving."""


class FilterWheelDevice:
    """Low-level driver for the QHYCCD filter wheel."""

    def __init__(self, device_config: DeviceConfig):
        self._config = device_config

        # Serial settings (fixed by the QHYCCD protocol)
        self._baudrate = 9600
        self._timeout = device_config.timeout

        # Connection state
        self._serial: serial.Serial | None = None
        self._serial_lock = threading.Lock()
        self._connected = False
        self._connecting = False
        self._aborting = False

        # Motion tracking
        self._moving = False


    #######################################
    # ASCOM Methods Common To All Devices #
    #######################################
    def connect(self):
        """Kick off an async connect: open serial, then home in a background thread.

        Per IConnectV2, `connecting` stays True and `connected` stays False until
        homing completes; only then does `connected` flip to True.
        """
        if self._connecting or self._connected:
            return

        self._connecting = True
        try:
            self._serial = serial.Serial(
                port=self._config.serial_port,
                baudrate=self._baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
        except Exception as e:
            logger.error(f"Connection error opening serial: {e}")
            self._connecting = False
            self._connected = False
            raise

        # Filter wheel homes when first powered and when first connected.
        # The homing thread is responsible for flipping both _connected and _connecting.
        self._moving = True
        threading.Thread(target=self._connect_home, args=(0,), daemon=True).start()

    def _connect_home(self, target: int):
        """Background thread: run the initial home, then mark the device connected."""
        try:
            self._moving_timer(target)
            if self._aborting:
                # disconnect() asked us to stop; do not flip _connected to True
                return
            self._connected = True
            logger.info(f"Connected to filter wheel: {self._config.entity}")
        except Exception as e:
            logger.error(f"Homing failed during connect: {e}")
            self._connected = False
            if self._serial and self._serial.is_open:
                try:
                    self._serial.close()
                except Exception:
                    pass
            self._serial = None
        finally:
            self._connecting = False

    @property
    def connected(self) -> bool:
        return self._connected

    @connected.setter
    def connected(self, value: bool):
        if value and not self._connected:
            self.connect()
        elif not value and self._connected:
            self.disconnect()

    @property
    def connecting(self) -> bool:
        return self._connecting

    def disconnect(self):
        """Close serial connection.

        If a connect is in progress, signal it to abort and wait briefly so the
        background homing thread cannot flip ``_connected`` back to True after
        we return.
        """
        if self._connecting:
            self._aborting = True
            self._moving = False  # break _moving_timer's polling loop
            deadline = time.time() + 5
            while self._connecting and time.time() < deadline:
                time.sleep(0.05)

        if self._serial and self._serial.is_open:
            self._serial.close()

        self._connected = False
        self._serial = None
        self._aborting = False
        logger.info(f"Disconnected from filter wheel: {self._config.entity}")

    @property
    def entity(self) -> str:
        return self._config.entity

    ###########################
    # IFilterWheel properties #
    ###########################
    @property
    def focus_offsets(self) -> list:
        return self._config.focus_offsets

    @property
    def names(self) -> list:
        return self._config.names

    @property
    def position(self) -> int:
        """Return the current filter position (0–6), or -1 if moving."""
        if self._moving:
            return -1
        return self._read_position()

    @position.setter
    def position(self, value: int):
        """Command the wheel to move to *value* (0–9; protocol writes one ASCII digit)."""
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Not connected to filter wheel")

        # The QHYCCD protocol is a single ASCII digit; multi-byte writes would corrupt it.
        if not 0 <= value <= 9:
            raise ValueError(
                f"Position {value} out of single-digit range (0-9) for QHYCCD protocol"
            )

        # If the position is set too early (during a move), the controller gets stuck
        if self._moving:
            raise FilterWheelBusyError("Filter wheel is currently moving")

        try:
            with self._serial_lock:
                self._serial.write(f"{value}".encode())
        except Exception as e:
            logger.error(f"Failed to set position: {e}")
            raise

        self._moving = True
        time.sleep(1)
        threading.Thread(target=self._run_move, args=(value,), daemon=True).start()

        logger.info(f"Moving to position {value}")

    def _run_move(self, target: int):
        """Background thread wrapper around _moving_timer that logs failures."""
        try:
            self._moving_timer(target)
        except Exception as e:
            logger.error(f"Move to position {target} failed: {e}")
            self._moving = False

    @property
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


    ####################
    # Internal helpers #
    ####################
    def _read_position(self) -> int:
        """Query the filter wheel for its current position.

        Sends 'NOW' and reads a single byte back.  Returns the position
        as an integer (0–6), or -1 if the position cannot be determined
        (e.g. wheel is mid-travel or communication fails).

        Retries up to 3 times on empty responses before giving up.
        """
        if not self._serial or not self._serial.is_open:
            logger.error("Serial port not open")
            return -1

        empty_count = 0

        while True:
            try:
                with self._serial_lock:
                    self._serial.reset_input_buffer()
                    self._serial.write(b"NOW")
                    out = self._serial.read()

                if out == b"":
                    empty_count += 1
                    if empty_count >= 3:
                        return -1
                    continue
                else:
                    empty_count = 0

                return int(out.decode())

            except (TypeError, ValueError):
                return -1
            except Exception as e:
                logger.error(f"Failed to read position: {e}")
                raise

    def _moving_timer(self, target: int):
        """Background thread that polls position until the wheel reaches *target*.

        The QHYCCD filter wheel does not provide a hardware "moving" flag, so
        this thread periodically queries the position and clears the
        ``_moving`` flag once the target is reached (or on timeout).
        """
        time.sleep(1)
        t0 = time.time()

        while self._moving:
            current = self._read_position()
            logger.debug(f"Current position = {current}, Target position = {target}")
            if current == target:
                self._moving = False
                time.sleep(1)
                break
            if (time.time() - t0) > self._timeout:
                self._moving = False
                raise RuntimeError("Timed out while waiting for filter wheel to move")
            time.sleep(1)

        # Sleep again to prevent
        time.sleep(1)
