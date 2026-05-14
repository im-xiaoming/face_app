(function () {
  const PROCESS_INTERVAL_MS = 500;
  const STABLE_FRAMES_REQUIRED = 2;
  const MIN_FACE_WIDTH = 0.3;
  const MAX_FACE_WIDTH = 0.7;
  const CENTER_MIN = 0.32;
  const CENTER_MAX = 0.68;
  const MIN_BRIGHTNESS = 45;
  const MAX_BRIGHTNESS = 220;
  const CENTER_YAW_LIMIT = 0.035;
  const SIDE_YAW_LIMIT = 0.055;

  const STEPS = [
    {
      pose: 'front',
      message: 'Nhin thang vao camera',
      direction: '',
      passed: (face) => Math.abs(face.yawRatio) <= CENTER_YAW_LIMIT,
    },
    {
      pose: 'left',
      message: 'Quay nhe dau sang trai',
      direction: 'left',
      passed: (face) => face.yawRatio >= SIDE_YAW_LIMIT,
    },
    {
      pose: 'right',
      message: 'Quay nhe dau sang phai',
      direction: 'right',
      passed: (face) => face.yawRatio <= -SIDE_YAW_LIMIT,
    },
  ];

  let faceMesh = null;
  let active = false;
  let sending = false;
  let lastProcessedAt = 0;
  let stepIndex = 0;
  let stableFrames = 0;
  let captured = [];

  function el(id) {
    return document.getElementById(id);
  }

  function showUiFeedback(message, direction) {
    const status = el('status');
    const hint = el('camera-hint');
    const arrow = el('direction-arrow');

    if (hint) hint.textContent = message;
    if (status) {
      status.textContent = message;
      status.style.display = 'block';
    }
    if (arrow) {
      arrow.className = direction ? `direction-arrow ${direction}` : 'direction-arrow';
    }
  }

  function setGuide(ok) {
    const guide = document.querySelector('.face-guide');
    if (!guide) return;
    guide.classList.toggle('ready', ok);
    guide.classList.toggle('warn', !ok);
  }

  function markStepDone(pose) {
    const step = el(`step-${pose}`);
    if (step) step.classList.add('done');
  }

  function waitForVideo(video) {
    if (video.videoWidth && video.videoHeight) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const timeout = window.setTimeout(() => {
        reject(new Error('Khong the mo camera'));
      }, 5000);

      video.addEventListener('loadedmetadata', () => {
        window.clearTimeout(timeout);
        resolve();
      }, { once: true });
    });
  }

  function getBrightness(video) {
    const canvas = document.createElement('canvas');
    canvas.width = 48;
    canvas.height = 36;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let total = 0;

    for (let i = 0; i < pixels.length; i += 4) {
      total += 0.299 * pixels[i] + 0.587 * pixels[i + 1] + 0.114 * pixels[i + 2];
    }
    return total / (pixels.length / 4);
  }

  function averageX(landmarks, indexes) {
    return indexes.reduce((sum, index) => sum + landmarks[index].x, 0) / indexes.length;
  }

  function analyzeFace(results) {
    const video = el('camera');
    const faces = results.multiFaceLandmarks || [];

    if (faces.length === 0) {
      return { ok: false, reason: 'Khong thay khuon mat' };
    }
    if (faces.length > 1) {
      return { ok: false, reason: 'Chi giu mot khuon mat trong khung' };
    }

    const landmarks = faces[0];
    let minX = 1;
    let maxX = 0;
    let minY = 1;
    let maxY = 0;

    landmarks.forEach((point) => {
      minX = Math.min(minX, point.x);
      maxX = Math.max(maxX, point.x);
      minY = Math.min(minY, point.y);
      maxY = Math.max(maxY, point.y);
    });

    const width = maxX - minX;
    const centerX = minX + width / 2;
    const centerY = minY + (maxY - minY) / 2;
    const brightness = getBrightness(video);

    if (width < MIN_FACE_WIDTH) {
      return { ok: false, reason: 'Dua mat lai gan hon' };
    }
    if (width > MAX_FACE_WIDTH) {
      return { ok: false, reason: 'Lui ra xa mot chut' };
    }
    if (centerX < CENTER_MIN || centerX > CENTER_MAX || centerY < 0.25 || centerY > 0.75) {
      return { ok: false, reason: 'Dua mat vao giua khung' };
    }
    if (brightness < MIN_BRIGHTNESS) {
      return { ok: false, reason: 'Tang anh sang len' };
    }
    if (brightness > MAX_BRIGHTNESS) {
      return { ok: false, reason: 'Giam anh sang truc tiep' };
    }

    const leftEyeX = averageX(landmarks, [33, 133]);
    const rightEyeX = averageX(landmarks, [362, 263]);
    const eyeMidX = (leftEyeX + rightEyeX) / 2;
    const noseX = landmarks[1].x;

    return {
      ok: true,
      yawRatio: (noseX - eyeMidX) / width,
    };
  }

  function captureCurrentFrame() {
    const video = el('camera');
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);

    return new Promise((resolve) => {
      canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.92);
    });
  }

  async function completeStep(step) {
    const blob = await captureCurrentFrame();
    if (!blob || !active) return;

    captured.push({ pose: step.pose, blob });
    markStepDone(step.pose);
    stableFrames = 0;
    stepIndex += 1;

    if (stepIndex >= STEPS.length) {
      await submitCapturedImages();
      return;
    }

    const nextStep = STEPS[stepIndex];
    showUiFeedback(nextStep.message, nextStep.direction);
  }

  async function submitCapturedImages() {
    active = false;
    showUiFeedback('Dang luu anh...', '');

    const dataTransfer = new DataTransfer();
    captured.forEach((item) => {
      dataTransfer.items.add(new File([item.blob], `${item.pose}.jpg`, { type: 'image/jpeg' }));
    });

    el('camera-images').files = dataTransfer.files;
    el('camera-poses').value = JSON.stringify(captured.map((item) => item.pose));
    stopCamera();
    el('camera-register-form').submit();
  }

  async function handleResults(results) {
    if (!active || stepIndex >= STEPS.length) return;

    const face = analyzeFace(results);
    const step = STEPS[stepIndex];

    if (!face.ok) {
      stableFrames = 0;
      setGuide(false);
      showUiFeedback(face.reason, step.direction);
      return;
    }

    if (!step.passed(face)) {
      stableFrames = 0;
      setGuide(false);
      showUiFeedback(step.message, step.direction);
      return;
    }

    stableFrames += 1;
    setGuide(true);

    if (stableFrames >= STABLE_FRAMES_REQUIRED) {
      await completeStep(step);
    } else {
      showUiFeedback('Giu yen...', step.direction);
    }
  }

  async function processLoop() {
    if (!active || !faceMesh) return;

    const now = performance.now();
    if (!sending && now - lastProcessedAt >= PROCESS_INTERVAL_MS) {
      sending = true;
      lastProcessedAt = now;
      try {
        await faceMesh.send({ image: el('camera') });
      } catch (err) {
        showUiFeedback(`Loi xu ly camera: ${err.message}`, '');
      } finally {
        sending = false;
      }
    }

    requestAnimationFrame(processLoop);
  }

  async function start() {
    const video = el('camera');
    if (!video) return;

    if (typeof FaceMesh === 'undefined') {
      showUiFeedback('Khong tai duoc FaceMesh', '');
      return;
    }

    stepIndex = 0;
    stableFrames = 0;
    captured = [];
    ['front', 'left', 'right'].forEach((pose) => {
      const step = el(`step-${pose}`);
      if (step) step.classList.remove('done');
    });

    try {
      await initCamera('camera');
      await waitForVideo(video);
    } catch (err) {
      showUiFeedback(err.message, '');
      return;
    }

    faceMesh = new FaceMesh({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
    });
    faceMesh.setOptions({
      maxNumFaces: 2,
      refineLandmarks: true,
      minDetectionConfidence: 0.75,
      minTrackingConfidence: 0.75,
      selfieMode: false,
    });
    faceMesh.onResults(handleResults);

    active = true;
    showUiFeedback(STEPS[0].message, STEPS[0].direction);
    requestAnimationFrame(processLoop);
  }

  window.initRegisterCamera = function initRegisterCamera() {
    const restartBtn = el('restart-camera-btn');
    if (restartBtn) {
      restartBtn.addEventListener('click', () => {
        stopCamera();
        active = false;
        start();
      });
    }
    start();
  };
}());
