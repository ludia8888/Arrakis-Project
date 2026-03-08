const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const statusEl = document.getElementById("status");
const overlayVideoEl = document.getElementById("overlayVideo");
const overlayCanvas = document.getElementById("overlayCanvas");
const overlayCtx = overlayCanvas.getContext("2d");
const confInput = document.getElementById("confInput");
const confValue = document.getElementById("confValue");
const imgszSelect = document.getElementById("imgszSelect");
const fpsSelect = document.getElementById("fpsSelect");
const objectsValue = document.getElementById("objectsValue");
const latencyValue = document.getElementById("latencyValue");
const throughputValue = document.getElementById("throughputValue");

const captureCanvas = document.createElement("canvas");
const captureCtx = captureCanvas.getContext("2d");

let sharedStream = null;
let inferenceTimer = null;
let requestInFlight = false;
let lastInferenceAt = 0;

function setStatus(message) {
  statusEl.textContent = message;
}

function syncCanvasSize() {
  const width = overlayVideoEl.videoWidth || 1280;
  const height = overlayVideoEl.videoHeight || 720;
  overlayCanvas.width = width;
  overlayCanvas.height = height;
  captureCanvas.width = width;
  captureCanvas.height = height;
}

function drawDetections(detections) {
  overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  overlayCtx.lineWidth = 3;
  overlayCtx.font = "600 18px 'Avenir Next', sans-serif";
  overlayCtx.textBaseline = "top";

  detections.forEach((detection) => {
    const x = detection.x1;
    const y = detection.y1;
    const width = detection.x2 - detection.x1;
    const height = detection.y2 - detection.y1;
    const label = `${detection.label} ${Math.round(detection.confidence * 100)}%`;

    overlayCtx.strokeStyle = "#f4a261";
    overlayCtx.fillStyle = "rgba(244, 162, 97, 0.16)";
    overlayCtx.strokeRect(x, y, width, height);
    overlayCtx.fillRect(x, y, width, height);

    const textWidth = overlayCtx.measureText(label).width + 16;
    const textY = Math.max(0, y - 30);
    overlayCtx.fillStyle = "#162026";
    overlayCtx.fillRect(x, textY, textWidth, 28);
    overlayCtx.fillStyle = "#fffaf4";
    overlayCtx.fillText(label, x + 8, textY + 5);
  });
}

async function sendFrame() {
  if (!sharedStream || requestInFlight || overlayVideoEl.readyState < 2) {
    return;
  }

  requestInFlight = true;
  syncCanvasSize();
  captureCtx.drawImage(overlayVideoEl, 0, 0, captureCanvas.width, captureCanvas.height);
  const image = captureCanvas.toDataURL("image/jpeg", 0.72);

  const startedAt = performance.now();

  try {
    const response = await fetch("/api/infer", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        image,
        conf: Number(confInput.value),
        imgsz: Number(imgszSelect.value),
      }),
    });

    if (!response.ok) {
      throw new Error(`Inference failed with status ${response.status}`);
    }

    const payload = await response.json();
    drawDetections(payload.detections);

    const finishedAt = performance.now();
    const latency = finishedAt - startedAt;
    const throughput = lastInferenceAt ? 1000 / (finishedAt - lastInferenceAt) : 0;
    lastInferenceAt = finishedAt;

    objectsValue.textContent = `${payload.detections.length} objects`;
    latencyValue.textContent = `${Math.round(latency)} ms`;
    throughputValue.textContent = `${throughput.toFixed(1)} fps`;
    setStatus("Inference is running. Adjust confidence if the boxes feel too noisy.");
  } catch (error) {
    console.error(error);
    setStatus("Inference request failed. Check that the local server is still running.");
  } finally {
    requestInFlight = false;
  }
}

function startInferenceLoop() {
  stopInferenceLoop();
  const intervalMs = 1000 / Number(fpsSelect.value);
  inferenceTimer = window.setInterval(sendFrame, intervalMs);
}

function stopInferenceLoop() {
  if (inferenceTimer) {
    window.clearInterval(inferenceTimer);
    inferenceTimer = null;
  }
}

function stopSharing() {
  stopInferenceLoop();

  if (sharedStream) {
    sharedStream.getTracks().forEach((track) => track.stop());
    sharedStream = null;
  }

  overlayVideoEl.srcObject = null;
  overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  startButton.disabled = false;
  stopButton.disabled = true;
  objectsValue.textContent = "0 objects";
  latencyValue.textContent = "0 ms";
  throughputValue.textContent = "0 fps";
  setStatus("Stopped. Start a new share when you want to test another video.");
}

async function startSharing() {
  try {
    setStatus("Choose the YouTube tab or the browser window that is playing video.");
    sharedStream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        frameRate: 30,
      },
      audio: false,
    });

    const [track] = sharedStream.getVideoTracks();
    track.addEventListener("ended", stopSharing);

    overlayVideoEl.srcObject = sharedStream;

    await overlayVideoEl.play();
    syncCanvasSize();

    startButton.disabled = true;
    stopButton.disabled = false;
    setStatus("Share active. The overlay view should track the same YouTube image you selected.");
    startInferenceLoop();
  } catch (error) {
    console.error(error);
    setStatus("Share request was cancelled or blocked. Try again and select the YouTube tab.");
    stopSharing();
  }
}

confInput.addEventListener("input", () => {
  confValue.textContent = Number(confInput.value).toFixed(2);
});

fpsSelect.addEventListener("change", () => {
  if (sharedStream) {
    startInferenceLoop();
  }
});

startButton.addEventListener("click", startSharing);
stopButton.addEventListener("click", stopSharing);

window.addEventListener("resize", syncCanvasSize);

setStatus("Ready. Start by sharing the YouTube tab or browser window.");
