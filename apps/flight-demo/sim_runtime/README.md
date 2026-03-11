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
- `ARRAKIS_ARDUPILOT_DEFAULTS=Tools/autotest/default_params/quadplane.parm,apps/flight-demo/sim_runtime/params/quadplane_demo.parm`
- `ARRAKIS_ARDUPILOT_CONNECTION=udp:127.0.0.1:14550`
- `ARRAKIS_ARDUPILOT_VIDEO_SOURCE=`  
  Keep this empty for the current path because FlightGear is view-only and does not feed the browser video panel.

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
