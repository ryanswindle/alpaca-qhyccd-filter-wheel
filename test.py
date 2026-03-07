import time

from alpaca.filterwheel import FilterWheel
from config import config


fw = FilterWheel(f"{config.server.host}:{config.server.port}", 0)

print(f"  Name:   {fw.Name}")
print(f"  Driver: {fw.DriverVersion}\n")

# Connect
print("Connecting...")
fw.Connected = True
print(f"  Connected: {fw.Connected}")

# Wait for initial homing
print("\nWaiting for initial homing...")
t0 = time.time()
while fw.Position == -1:
    time.sleep(1)
    if (time.time() - t0) > 60:
        print("  Timed out waiting for homing")
        break
print(f"  Position: {fw.Position}")

# Filter names and focus offsets
print(f"  Names: {fw.Names}")
print(f"  FocusOffsets: {fw.FocusOffsets}")

# Cycle through positions
for pos in [1, 2, 3, 4, 5, 6, 0]:
    print(f"\nMoving to position {pos}...")
    fw.Position = pos
    t0 = time.time()
    while fw.Position == -1:
        time.sleep(1)
        if (time.time() - t0) > 60:
            print("  Timed out waiting for move")
            break
    print(f"  Position: {fw.Position}")
    time.sleep(3)

# Disconnect
print("\nDisconnecting...")
fw.Connected = False
print(f"  Connected: {fw.Connected}")
print()