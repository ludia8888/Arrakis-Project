# Perception Backend Notes

This layer exists so the Arrakis mission/state machine does not care which image model the AI team is shipping.

## Design intent

- `DetectorService` owns queueing, cadence, recent event aggregation, and runtime state.
- Model-specific inference lives behind the perception backend interface.
- The rest of the system should only see normalized `DetectionBox` outputs and a backend `mode` string.

## Current backends

- `YoloPerceptionBackend`
  - Loads `.pt` weights through Ultralytics
  - Supports the current `person / vehicle` detector flow
- `SyntheticPerceptionBackend`
  - Mock/demo fallback
  - Also acts as a fallback when a real model loads but yields no detections on the mock stream

## Model selection

- The backend selection order is:
  1. `ARRAKIS_DETECTOR_MODEL_PATH`
  2. `./best.pt`
  3. `./runs/visdrone/.../best.pt`
  4. `./yolo26s.pt`
- If no usable model is found, the synthetic backend remains active.

## Future expansion

Additional model teams should fit into this layer by implementing the same interface, for example:

- `OnnxPerceptionBackend`
- `TensorRtPerceptionBackend`
- `RemotePerceptionBackend`

The goal is to let the AI team swap inference implementations without rewriting:

- `telemetry_hub`
- the mission state machine
- frontend state rendering
