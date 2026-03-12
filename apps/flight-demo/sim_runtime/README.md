# Arrakis VTOL Sim Runtime

The selected real-flight path is now:

- `ArduPilot`
- `sim_vehicle.py -f quadplane`
- optional `FlightGear` view-only rendering

This is the primary runtime path for the v1 demo. The older `Gazebo + zephyr` path remains in the tree only as an experimental fallback for future camera work.

## Why this path

- It matches the official ArduPilot QuadPlane simulation path.
- It avoids the current blocker we hit with `ardupilot_gazebo` Zephyr models not providing a true VTOL airframe.
- It preserves the Arrakis architecture:
  - `ArduPilotAdapter`
  - `pymavlink` connection
  - mission upload / mission-oriented execution
  - Arrakis mission/state/safety logic

## Primary local smoke

Environment probe:

```bash
cd apps/flight-demo/sim_runtime
./check_environment.sh
```

Runtime env template:

```bash
cd apps/flight-demo/sim_runtime
cp runtime.env.example runtime.env
```

The primary env values are:
- `ARRAKIS_ARDUPILOT_DIR`
- `ARRAKIS_ARDUPILOT_FRAME=quadplane`
- `ARRAKIS_ARDUPILOT_DEFAULTS=apps/flight-demo/sim_runtime/params/quadplane_demo.parm`
- `ARRAKIS_ARDUPILOT_CONNECTION=udp:0.0.0.0:14551`
- `ARRAKIS_VTOL_LANDING_APPROACH_MIN_M=140`
- `ARRAKIS_ARDUPILOT_VIDEO_SOURCE=`  
  Keep this empty for the current path because FlightGear is view-only and does not feed the browser video panel.
- `ARRAKIS_FLIGHTGEAR_BIN=/Applications/FlightGear.app/Contents/MacOS/FlightGear`
- `ARRAKIS_FLIGHTGEAR_AIRCRAFT=Rascal110-JSBSim`
- `ARRAKIS_FLIGHTGEAR_AIRCRAFT_DIR=$HOME/Developer/ardupilot/Tools/autotest/aircraft`
- `ARRAKIS_FLIGHTGEAR_NATIVE_FDM_PORT=5503`
- `ARRAKIS_FLIGHTGEAR_AIRPORT=YSCB`
- `ARRAKIS_FLIGHTGEAR_GEOMETRY=1280x720`
- `ARRAKIS_FLIGHTGEAR_DISABLE_SPLASH=1`
- `ARRAKIS_FLIGHTGEAR_VIEW_NUMBER=2`
- `ARRAKIS_FLIGHTGEAR_INTERNAL_VIEW=0`
- `ARRAKIS_FLIGHTGEAR_CHASE_DISTANCE_M=-18`

Important:
- `sim_vehicle.py -f quadplane` already injects the stock `default_params/quadplane.parm` internally. `ARRAKIS_ARDUPILOT_DEFAULTS` should therefore point only to Arrakis-specific override params.
- `sim_vehicle.py --out` is a MAVProxy forwarding path, not a direct ArduPilot output path.
- `sim_vehicle.py` shells out to `mavproxy.py`. On macOS hosts this often lives under `$HOME/Library/Python/<ver>/bin`, while Ubuntu VM guests usually use `$HOME/.local/bin`.
- `common.sh` now auto-discovers `mavproxy.py` and prepends its directory to `PATH`, but you can also set `ARRAKIS_MAVPROXY_BIN` explicitly if needed.
- In QEMU user-networking mode, the guest should forward MAVLink to the host-reachable address `10.0.2.2:14551`, while the macOS host backend listens on `udp:0.0.0.0:14551`.
- `run_backend_ardupilot.sh` loads `runtime.env` through [`common.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/common.sh), so quoted values such as `ARRAKIS_MAVPROXY_ARGS="--daemon --non-interactive --nowait"` are supported.
- `common.sh` also expands `$HOME`, `${HOME}`, and leading `~/` in `runtime.env`, so host/guest env files can safely use absolute home-based paths.
- `sim_vehicle.py -f quadplane` must run with `--enable-fgview`, otherwise FlightGear opens but never receives live FDM updates.
- `run_flightgear_view.sh` now launches `FlightGear` directly rather than going through `fg_plane_view.sh` or `fg_quad_view.sh`.
- The current external view still uses a surrogate fixed-wing model (`Rascal110-JSBSim`), because the ArduPilot autotest assets do not ship a real quadplane 3D model for FlightGear.
- `ARRAKIS_FLIGHTGEAR_DISABLE_SPLASH=1` suppresses the heavy aircraft splash screen so the view reaches the live scene faster.
- On macOS, the FlightGear app bundle injects `FG_LAUNCHER=1` through `Info.plist`. `run_flightgear_view.sh` explicitly unsets it so `--aircraft`, `--fdm`, and other direct `fgfs` arguments are honored.
- If `mavproxy.py` still fails with missing module errors on macOS hosts, install the runtime dependencies in the same user Python environment:
  `python3 -m pip install --user --break-system-packages MAVProxy future gnureadline`

Bootstrap a local macOS runtime:

```bash
cd apps/flight-demo/sim_runtime
./bootstrap_macos_runtime.sh
```

Primary SITL launcher:

```bash
cd apps/flight-demo/sim_runtime
./run_ardupilot_quadplane.sh
```

Optional FlightGear view-only renderer:

```bash
cd apps/flight-demo/sim_runtime
./run_flightgear_view.sh
```

Backend on the real adapter:

```bash
cd apps/flight-demo/sim_runtime
./run_backend_ardupilot.sh
```

Adapter smoke once SITL is up:

```bash
cd apps/flight-demo/sim_runtime
../../.venv/bin/python smoke_ardupilot_sitl.py
```

## Expected runtime split

For the current official QuadPlane path:

- `sim_vehicle.py -f quadplane` provides the real flight dynamics
- `FlightGear` is optional and view-only
- the Arrakis browser video panel will not receive a real camera feed unless a separate source is attached later

That means the current real-flight goal is:
- validate connection
- validate telemetry
- validate mission upload
- validate VTOL takeoff / outbound / return / recovery / landing semantics

Not yet:
- real simulator camera into the browser video panel

## Local run sequence

Terminal 1, QuadPlane SITL:

```bash
cd apps/flight-demo/sim_runtime
./run_ardupilot_quadplane.sh
```

Terminal 2, optional FlightGear view:

```bash
cd apps/flight-demo/sim_runtime
./run_flightgear_view.sh
```

Terminal 3, backend:

```bash
cd apps/flight-demo/sim_runtime
./run_backend_ardupilot.sh
```

Terminal 4, adapter smoke:

```bash
cd apps/flight-demo/sim_runtime
../../.venv/bin/python smoke_ardupilot_sitl.py
```

## Ubuntu VM fallback

If local macOS setup becomes painful, keep the same QuadPlane runtime path and move only SITL into Ubuntu VM.

Bootstrap the VM:

```bash
cd apps/flight-demo/sim_runtime
./bootstrap_ubuntu_vm_runtime.sh
```

Provision the VM workspace:

```bash
cd apps/flight-demo/sim_runtime
./provision_ubuntu_vm_workspace.sh
```

Write a guest runtime env inside the VM:

```bash
cd apps/flight-demo/sim_runtime
./write_vm_guest_runtime_env.sh
```

Verify VM runtime:

```bash
cd apps/flight-demo/sim_runtime
./check_ubuntu_vm_runtime.sh
```

Inside the VM, run:

```bash
cd apps/flight-demo/sim_runtime
./run_ardupilot_quadplane.sh
```

Optional in the VM:

```bash
cd apps/flight-demo/sim_runtime
./run_flightgear_view.sh
```

On the macOS host, write a VM-targeted env file:

```bash
cd apps/flight-demo/sim_runtime
./write_vm_host_runtime_env.sh <vm-ip>
```

This host env intentionally binds:

```bash
ARRAKIS_ARDUPILOT_CONNECTION=udp:0.0.0.0:14550
```

because the guest MAVProxy forwards UDP to the host rather than the host dialing into the VM IP.

Then start the backend on the host:

```bash
cd apps/flight-demo/sim_runtime
./run_backend_ardupilot.sh
```

## Experimental Gazebo path

The following scripts remain in the repository for later camera work, but they are not the primary runtime anymore:

- `run_gazebo_zephyr.sh`
- `run_ardupilot_zephyr.sh`
- `build_ardupilot_gazebo.sh`
- `enable_camera_stream.sh`
- `install_gz_harmonic.sh`

Use them only when revisiting a simulator camera integration path.
