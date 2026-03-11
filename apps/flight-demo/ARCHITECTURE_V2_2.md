# Arrakis VTOL 데모 아키텍처 계획 v2.2

## Summary

- 새 데모는 `ArduPilot로 먼저 시작`하되, 구조는 `flight controller adapter 분리 + Arrakis mission/state machine 독립`으로 고정한다.
- 목표는 사용자가 지도에서 코스를 지정하면 `VTOL 고정익`이 `수직 이륙 -> 고정익 전환 -> outbound -> return -> 감속/회복 -> 멀티콥터 전환 -> 수직 착륙`을 수행하고, 브라우저에서 `지도 + 상태 패널 + 시뮬레이터 영상 + 탐지 이벤트`를 보여주는 것이다.
- v1은 `단일 VTOL 기체`, `왕복 자율 순찰`, `시뮬레이터 영상`, `탐지`, `battery RTL`, `geofence abort`까지만 포함한다.
- ArduPilot/PX4 차이는 adapter 안에 가두고, Arrakis core는 공통 인터페이스와 공통 상태 스키마만 본다.

## Key Changes

### 1. 코드 구조와 경계

- `apps/flight-demo/` 아래에 새 데모를 분리한다.
- 계층은 아래 네 개로 고정한다.
  - `frontend`: 지도, 영상, 상태 패널, 컨트롤
  - `arrakis_core`: route planner, mission state machine, safety manager, telemetry hub
  - `flight_adapters`: `ArduPilotAdapter`, `PX4Adapter` 자리
  - `sim_runtime`: SITL/Gazebo 실행 스크립트와 환경 문서
- 규칙:
  - 프론트는 adapter를 직접 모른다.
  - mission/state machine은 flight stack 전용 API를 직접 호출하지 않는다.
  - detector와 video는 simulator implementation을 직접 읽지 않고 adapter가 노출하는 공통 video 인터페이스를 사용한다.

### 2. Flight Controller Adapter 인터페이스

- adapter 인터페이스는 아래 메서드로 고정한다.
  - `connect()`
  - `arm()`
  - `takeoff_multicopter(target_alt_m)`
  - `upload_roundtrip_mission(route_spec)`
  - `start_mission()`
  - `transition_to_fixedwing()`
  - `prepare_multicopter_recovery(recovery_spec)`
  - `transition_to_multicopter()`
  - `return_to_home()`
  - `land_vertical()`
  - `abort(reason)`
  - `reset()`
  - `get_snapshot()`
  - `current_leg()`
  - `stream_telemetry(callback)`
  - `stream_video(callback)`
- `stream_video(callback)`가 camera source의 유일한 공통 진입점이다.
  - ArduPilot v1은 Gazebo 카메라 source를 adapter 내부에서 구독/수집
  - detector_service와 MJPEG worker는 adapter video stream만 소비
- telemetry snapshot schema는 아래로 고정한다.
  - `timestamp`
  - `lat`, `lon`, `alt_m`
  - `airspeed_mps`
  - `groundspeed_mps`
  - `battery_percent`
  - `armed`
  - `flight_mode`
  - `vtol_state`
  - `mission_index`
  - `home_distance_m`
  - `geofence_breached`
  - `sim_rtf`
- v1 구현은 `ArduPilotAdapter`만 제공한다.
- `PX4Adapter`는 같은 인터페이스를 따르는 향후 구현 대상으로만 남긴다.

### 3. Arrakis Core

- Arrakis core는 아래 모듈로 고정한다.
  - `route_planner`
  - `mission_state_machine`
  - `mission_executor`
  - `safety_manager`
  - `telemetry_hub`
  - `state_payload_assembler`
  - `video_service`
  - `detector_service`
  - `perception_backends`
- mission phase는 아래 문자열로 고정한다.
  - `IDLE`
  - `ARMING`
  - `TAKEOFF_MC`
  - `TRANSITION_FW`
  - `OUTBOUND`
  - `RETURN`
  - `PRE_MC_RECOVERY`
  - `TRANSITION_MC`
  - `LANDING`
  - `RTL_BATTERY`
  - `ABORT_GEOFENCE`
  - `ABORT_MANUAL`
  - `COMPLETE`
- 상태 머신은 Arrakis core가 소유한다.
- 실제 round-trip mission 실행 순서는 `mission_executor`가 소유한다.
- adapter는 “명령 실행 + telemetry/video 공급”만 담당한다.
- detector service는 queueing, cadence, event aggregation을 담당하고, 실제 모델 추론은 `perception_backends` 경계 뒤로 숨긴다.
- 즉 이미지 인식 모델은 비행 스택과 마찬가지로 교체 가능한 backend로 취급한다.
- `telemetry_hub`는 telemetry/safety 상태만 소유한다.
- `state_payload_assembler`는 telemetry, route progress, detector/simulator state를 프론트용 `StatePayload`로 조립한다.
- `video_service`는 camera frame, detector runtime, JPEG/MJPEG용 video state를 담당한다.
- `reset()`은 실행 중 mission thread를 먼저 취소하고 정리한 뒤 adapter/video/state를 초기화해야 한다.
- 각 구조화된 모듈은 `arrakis.*` 네임스페이스 logger를 가져야 한다.
  - 예: `arrakis.controller`, `arrakis.executor`, `arrakis.adapter.ardupilot`
  - 모듈 경계를 넘는 호출은 호출 전/후와 소요 시간을 로그로 남긴다.
- adapter public 메서드 계측은 wrapper/proxy로 일괄 적용해, 새 adapter 구현이 들어와도 같은 로그 계약을 유지한다.
- adapter 계약은 `ABC`에만 의존하지 않는다.
  - `FlightControllerAdapterContract` runtime protocol validator를 통해 초기화 시점에 계약 위반을 바로 실패시킨다.

### 4. Route와 Geofence 정책

- 사용자는 지도에서 2~12개의 waypoint를 찍는다.
- `route_planner`는 outbound route와 reversed return route를 자동 생성한다.
- geofence source는 사용자 입력이 아니라 `route 기반 자동 생성`으로 고정한다.
- 생성 규칙:
  - home + outbound + return 전체 polyline을 기준으로 corridor polygon 생성
  - corridor half-width 기본값: `120m`
  - home 주변 safety bubble radius: `80m`
  - 모든 waypoint와 return path가 polygon 내부에 포함되도록 보정
- 프론트는 route 생성 직후 geofence polygon을 항상 표시한다.
- v1에서는 사용자가 geofence를 직접 그리지 않는다.
- `safety_manager`는 adapter snapshot의 위치와 generated geofence polygon을 사용해 breach를 판단한다.

### 5. Recovery/Transition 정책

- `prepare_multicopter_recovery(recovery_spec)`의 기본 spec:
  - trigger point: return 마지막 waypoint 통과 후
  - recovery center: home 상공
  - target loiter radius: `35m`
  - target altitude: `50m`
  - primary speed threshold: `<= 14 m/s`
  - primary home distance threshold: `<= 80m`
  - primary altitude deviation: `<= 12m`
  - primary dwell: `3s`
  - primary timeout: `25s`
- primary 성공 조건:
  - `airspeed_mps <= 14`
  - `home_distance_m <= 80`
  - `abs(alt_m - target_alt_m) <= 12`
  - 위 조건이 연속 `3초` 유지
- primary 실패 조건:
  - `25초` 내 성공 조건 미충족
  - geofence breach
  - battery threshold 하회
- 실패 시 우선순위:
  - `RTL_BATTERY` 또는 `ABORT_GEOFENCE`가 우선
  - 그 외는 `return_to_home()` 재시도 후 multicopter transition fallback 1회
- fallback recovery는 `완화된 기준`을 사용한다.
  - fallback speed threshold: `<= 17 m/s`
  - fallback home distance threshold: `<= 110m`
  - fallback altitude deviation: `<= 18m`
  - fallback dwell: `2s`
  - fallback timeout: `18s`
- fallback 성공 조건:
  - `airspeed_mps <= 17`
  - `home_distance_m <= 110`
  - `abs(alt_m - target_alt_m) <= 18`
  - 위 조건이 연속 `2초` 유지
- fallback 목적:
  - primary 기준으로 회복이 안 되는 경우, transition 기회를 한 번 더 주되 위험하게 완화하지는 않음
- fallback도 실패하면:
  - v1에서는 autonomous emergency land는 구현하지 않음
  - 상태는 operator intervention required로 표시하고 `ABORT_MANUAL` 계열 종료 상태로 고정

### 6. Video, Detector, WebSocket

- 영상은 adapter의 `stream_video()`를 통해 최신 프레임을 수신한다.
- video worker는 latest-frame overwrite queue를 사용한다.
- MJPEG 정책:
  - JPEG quality: `75`
  - default width target: `1280`
  - fallback width target: `960`
  - target stream fps: `12`
- detector 정책:
  - model backend selection order: `ARRAKIS_DETECTOR_MODEL_PATH -> best.pt -> yolo26s.pt`
  - classes: `person`, `vehicle`
  - default `imgsz=960`
  - default cadence: `2프레임당 1회`
  - fallback: `imgsz=768` 또는 `3프레임당 1회`
- detector 구현 규칙:
  - `DetectorService`는 public runtime API를 유지한다.
  - 실제 추론 엔진은 `YoloPerceptionBackend`, `SyntheticPerceptionBackend` 같은 backend 클래스로 분리한다.
  - 향후 `ONNX`, `TensorRT`, remote inference도 같은 경계에 추가한다.
- degrade rules:
  - `sim_rtf < 0.9` 5초 지속 시 detector degrade step 1
  - `sim_rtf < 0.7` 또는 MJPEG latency 급등 시 detector degrade step 2
  - degrade는 detector와 MJPEG 품질만 낮추고 mission loop는 유지
- 위 `RTF` 기준값은 현재 `provisional`이다.
  - mock adapter의 `sim_rtf`는 실제 SITL/Gazebo/Jetson 환경을 대변하지 않는다.
  - ArduPilot SITL이 실제로 붙은 뒤, M4 Rosetta 경로와 Ubuntu VM fallback 경로에서 먼저 재측정한다.
  - Jetson 경로에서는 별도 프로파일링을 수행하고 threshold를 다시 보정한다.
  - 최종 degrade 정책은 `RTF` 하나만이 아니라 `video_latency_ms`, detector inference time, frame drop rate도 함께 본다.
- `WS /ws/state`는 `5 Hz`로 고정한다.
- WebSocket payload schema는 아래로 고정한다.
  - `timestamp`
  - `mission_phase`
  - `abort_reason | null`
  - `telemetry`: snapshot schema 전체
  - `route_progress`
    - `outbound_total`
    - `return_total`
    - `current_leg`
    - `current_waypoint_index`
    - `next_waypoint`
  - `detector`
    - `enabled`
    - `mode`
    - `last_inference_ms`
    - `objects_visible`
    - `recent_events`
  - `simulator`
    - `connected`
    - `camera_connected`
    - `rtf`
    - `video_fps`
    - `video_latency_ms`
- `recent_events`는 최근 10초, 최대 20개로 제한한다.
- FastAPI 앱은 import 시점에 controller를 전역 생성하지 않는다.
  - controller/adapter는 app lifespan에서 생성하고 shutdown 시 정리한다.
- `ARRAKIS_STATE_DUMP_PATH`가 설정되면 `StatePayload`를 JSONL로 파일에 기록한다.
  - 목적은 이상 동작 후 phase, telemetry, detector, simulator 상태를 재구성하는 블랙박스다.
- `GET /api/health`는 adapter 연결 상태, detector 상태, 마지막 telemetry 시각, simulator 상태, process memory를 반환한다.
  - 데모 시작 전 시스템 정상 여부를 빠르게 확인하는 용도다.
- 로컬 검증 기준 경로는 `check.sh`다.
  - backend compile, frontend build, adapter smoke test, mock full round trip을 한 번에 수행한다.

### 7. 프론트엔드 UX

- 레이아웃은 `지도 + 영상 + 상태 패널`로 고정한다.
- 지도 표시 요소:
  - outbound polyline
  - return polyline
  - home marker
  - current position marker
  - next waypoint 강조
  - geofence polygon 반투명 layer
- 상태 패널 표시 요소:
  - mission phase
  - VTOL state
  - battery
  - airspeed
  - altitude
  - next waypoint
  - geofence status
  - simulator RTF
  - abort reason
  - recent detector events
- 컨트롤:
  - `Set Route`
  - `Start Mission`
  - `Abort`
  - `Return Home`
  - `Reset`
- 프론트는 geofence breach 시
  - polygon edge highlight
  - abort reason banner
  - state panel reason text
  를 동시에 보여준다.

### 8. 구현 순서

- Step 1: skeleton
  - 앱 구조 분리
  - adapter interface
  - core module skeleton
  - WS schema 고정
- Step 2: mock adapter
  - route, phase, geofence, video placeholder, detector placeholder로 full UI 흐름 완성
- Step 3: ArduPilot adapter
  - telemetry mapping
  - video stream hookup
  - mission upload/start/rtl/land
- Step 4: recovery logic
  - `PRE_MC_RECOVERY`
  - primary/fallback success/failure/timeout 처리
- Step 5: detector integration
  - actual stream_video consumption
  - overlay + events
- Step 6: environment hardening
  - Rosetta path
  - UTM fallback doc
  - performance thresholds 검증

## Test Plan

- 아키텍처:
  - mock adapter만으로 full demo flow가 실행된다.
  - detector/video가 adapter 인터페이스만 사용한다.
  - Arrakis core는 adapter implementation을 교체해도 동일 state machine을 유지한다.
- Route/Geofence:
  - route 생성 직후 geofence polygon이 생성되고 표시된다.
  - geofence breach가 state panel과 지도에 동시에 반영된다.
- Recovery:
  - `PRE_MC_RECOVERY`에서 primary 기준으로 multicopter transition이 수행된다.
  - primary timeout 시 fallback 기준으로 한 번 더 recovery를 시도한다.
  - fallback도 실패하면 operator intervention required 상태가 표시된다.
- WebSocket:
  - `5 Hz` 상태 메시지가 schema대로 수신된다.
  - 프론트는 이 schema만으로 상태 패널을 갱신할 수 있다.
- 통합:
  - ArduPilot SITL에서 round trip 수행
  - battery threshold RTL 재현
  - geofence abort 재현
  - 영상 + detection overlay 동시 표시
- adapter contract:
  - `pytest tests/test_adapter_contract.py` 하나로 smoke test를 시작할 수 있어야 한다.
  - 최소 검증은 `connect -> arm -> get_snapshot -> current_leg -> telemetry/video callback` 순서로 수행한다.

## Assumptions

- v1은 ArduPilot 기반 단일 VTOL 데모다.
- geofence는 사용자 직접 입력이 아니라 route 기반 자동 생성이다.
- camera source 추상화도 adapter에 포함한다.
- emergency landing/autonomous fault tree는 v1 범위에서 제외한다.
- PX4는 이번에 구현하지 않지만, adapter 계약은 PX4도 수용할 수 있도록 유지한다.

## Critical Review Addendum

### 1. ArduPilot + Gazebo + M4 (Rosetta) 궁합

- ArduPilot SITL은 PX4보다 최신 Gazebo(Harmonic/Garden)와의 연동이 약간 더 까다로울 수 있다.
- `ardupilot_gazebo` 플러그인이 x86_64 환경(Rosetta)에서 컴파일될 때 그래픽 드라이버 이슈가 생길 수 있으므로, Step 1 스모크 테스트에서 이를 최우선으로 검증한다.
- Rosetta 경로에서 Gazebo 플러그인이 불안정하거나 카메라 transport가 흔들리면, 로컬 그래픽 스택을 억지로 붙잡지 않는다.
- 대안:
  - Gazebo와 SITL만 Ubuntu VM에서 실행
  - Arrakis 앱 계층은 macOS arm64에 유지
  - 영상과 telemetry는 adapter 경계 뒤에서 소켓 경유로 다시 가져온다

### 2. MAVSDK와 ArduPilot의 호환성

- MAVSDK는 PX4 전용 기능이 많기 때문에, ArduPilot adapter에서 `transition_to_fixedwing()`과 `transition_to_multicopter()`가 표준 MAVLink 명령 `DO_VTOL_TRANSITION`으로 정확히 매핑되는지 먼저 검증해야 한다.
- ArduPilot adapter의 기본 전략은 `MAVSDK 우선`이다.
- 하지만 다음 항목에서 MAVSDK가 원하는 수준으로 동작하지 않으면 adapter 내부 구현은 `pymavlink`로 내려간다.
  - VTOL transition
  - mode 변경
  - mission-level VTOL landing sequence
  - recovery/loiter 관련 저수준 제어
- 중요한 점은 Arrakis core와 프론트엔드는 이 내부 구현 차이를 모르게 유지하는 것이다.

### 3. 지연 시간(Latency) 관리

- `stream_video(callback)`로 들어온 영상을 detector와 MJPEG 워커가 다시 소비하는 구조에서는 프레임 복사 비용이 누적될 수 있다.
- v1은 구현 단순성을 위해 latest-frame overwrite queue와 OpenCV frame 전달을 허용한다.
- 하지만 다음 상황이 발생하면 transport를 adapter 내부에서 개선한다.
  - MJPEG latency 급등
  - detector cadence 유지 실패
  - simulator RTF 하락이 영상 경로와 결합되어 나타남
- 우선순위:
  1. latest-frame overwrite queue
  2. unnecessary copy 제거
  3. shared memory 또는 single-copy transport 검토
- 이 변경은 adapter/video worker 경계 안에서 끝내고, Arrakis core와 frontend API는 유지한다.

### 4. Detector Degrade Threshold Calibration

- 현재 코드에 들어간 detector degrade 기준은 `정책 자리 표시자`에 가깝다.
- 목적은 “비행 루프보다 detector 품질을 먼저 낮춘다”는 제어 우선순위를 고정하는 것이다.
- 하지만 실제 수치는 다음 환경에서 각각 실측 후 다시 정해야 한다.
  - mock adapter
  - M4 + Rosetta + ArduPilot SITL + Gazebo
  - Ubuntu VM fallback
  - Jetson 목표 런타임
- 따라서 현재의 `0.9 / 0.7` 기준은 설계상 초기값일 뿐, 제품 수준 threshold로 간주하지 않는다.
