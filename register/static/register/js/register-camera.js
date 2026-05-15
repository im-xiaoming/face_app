(function () {
  const PROCESS_INTERVAL_MS = 350;
  const STABLE_FRAMES_REQUIRED = 2;
  const MIN_FACE_WIDTH = 0.18;
  const MAX_FACE_WIDTH = 0.72;
  const MIN_BRIGHTNESS = 45;
  const MAX_BRIGHTNESS = 225;

  const OVAL_INSIDE_RATIO = 0.45;
  const OVAL_EXPAND_PX = 20;
  const MOTION_PX_LIMIT = 18;

  const FACE_OVAL_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365,
    379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93,
    234, 127, 162, 21, 54, 103, 67, 109,
  ];

  const FRONT_YAW_LIMIT = 0.04;
  const SIDE_YAW_LIMIT = 0.07;
  const SIDE_YAW_MAX = 0.55;
  const PITCH_LIMIT = 0.08;
  const SIDE_PITCH_LIMIT = 0.1;
  const ROLL_LIMIT_RAD = 0.14;
  const SIDE_ROLL_LIMIT_RAD = 0.18;

  const LM = {
    NOSE_TIP: 1,
    FOREHEAD: 10,
    CHIN: 152,
    LEFT_EYE_OUTER: 33,
    LEFT_EYE_INNER: 133,
    RIGHT_EYE_INNER: 362,
    RIGHT_EYE_OUTER: 263,
    LEFT_CHEEK: 234,
    RIGHT_CHEEK: 454,
  };

  const STEPS = [
    {
      pose: 'front',
      message: 'Nhìn thẳng vào camera',
      direction: '',
      passed: (f) =>
        Math.abs(f.yaw) <= FRONT_YAW_LIMIT &&
        Math.abs(f.pitch) <= PITCH_LIMIT &&
        Math.abs(f.roll) <= ROLL_LIMIT_RAD,
      hint: (f) => {
        if (Math.abs(f.roll) > ROLL_LIMIT_RAD) return 'Giữ đầu thẳng, đừng nghiêng em';
        if (Math.abs(f.pitch) > PITCH_LIMIT)
          return f.pitch > 0 ? 'Ngẩng đầu đi em' : 'Cúi đầu xuống một chút đi em';
        if (Math.abs(f.yaw) > FRONT_YAW_LIMIT) return 'Nhìn thẳng vào camera em';
        return 'Nhìn thẳng vào camera em';
      },
    },
    {
      pose: 'left',
      message: 'Quay đầu sang trái đi em',
      direction: 'left',
      passed: (f) =>
        f.yaw >= SIDE_YAW_LIMIT &&
        f.yaw <= SIDE_YAW_MAX &&
        Math.abs(f.pitch) <= SIDE_PITCH_LIMIT &&
        Math.abs(f.roll) <= SIDE_ROLL_LIMIT_RAD,
      hint: (f) => {
        if (Math.abs(f.roll) > SIDE_ROLL_LIMIT_RAD) return 'Giữ đầu thẳng, chỉ quay ngang';
        if (Math.abs(f.pitch) > SIDE_PITCH_LIMIT) return 'Giữ đầu ngang, đừng cúi em';
        if (f.yaw < SIDE_YAW_LIMIT) return 'Quay thếm sang trái em';
        if (f.yaw > SIDE_YAW_MAX) return 'Quay ít lài một chút em';
        return 'Quay đầu sang trái';
      },
    },
    {
      pose: 'right',
      message: 'Quay đầu sang phải đi em',
      direction: 'right',
      passed: (f) =>
        f.yaw <= -SIDE_YAW_LIMIT &&
        f.yaw >= -SIDE_YAW_MAX &&
        Math.abs(f.pitch) <= SIDE_PITCH_LIMIT &&
        Math.abs(f.roll) <= SIDE_ROLL_LIMIT_RAD,
      hint: (f) => {
        if (Math.abs(f.roll) > SIDE_ROLL_LIMIT_RAD) return 'Giữ đầu thẳng, chỉ quay ngang';
        if (Math.abs(f.pitch) > SIDE_PITCH_LIMIT) return 'Giữ đầu ngang, đừng cúi em';
        if (f.yaw > -SIDE_YAW_LIMIT) return 'Quay thêm sang phải đi em';
        if (f.yaw < -SIDE_YAW_MAX) return 'Quay ít lại mot chút đi em';
        return 'Quay đầu sang phai đi em';
      },
    },
  ];

  let faceMesh = null;
  let active = false;
  let sending = false;
  let lastProcessedAt = 0;
  let stepIndex = 0;
  let stableFrames = 0;
  let captured = [];
  let prevNose = null;
  let cachedOval = null;
  let brightnessCanvas = null;
  let brightnessCtx = null;

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
    if (!brightnessCanvas) {
      brightnessCanvas = document.createElement('canvas');
      brightnessCanvas.width = 48;
      brightnessCanvas.height = 36;
      brightnessCtx = brightnessCanvas.getContext('2d', { willReadFrequently: true });
    }
    brightnessCtx.drawImage(video, 0, 0, brightnessCanvas.width, brightnessCanvas.height);
    const pixels = brightnessCtx.getImageData(0, 0, brightnessCanvas.width, brightnessCanvas.height).data;
    let total = 0;

    for (let i = 0; i < pixels.length; i += 4) {
      total += 0.299 * pixels[i] + 0.587 * pixels[i + 1] + 0.114 * pixels[i + 2];
    }
    return total / (pixels.length / 4);
  }

  function getVisibleRegion(video, containerW, containerH) {
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    const containerAR = containerW / containerH;
    const videoAR = vw / vh;

    let visibleW, visibleH, offsetX, offsetY;
    if (videoAR > containerAR) {
      visibleH = vh;
      visibleW = vh * containerAR;
      offsetX = (vw - visibleW) / 2;
      offsetY = 0;
    } else {
      visibleW = vw;
      visibleH = vw / containerAR;
      offsetX = 0;
      offsetY = (vh - visibleH) / 2;
    }
    return { visibleW, visibleH, offsetX, offsetY, vw, vh };
  }

  function landmarkToContainer(lm, region, containerW, containerH) {
    const xPx = lm.x * region.vw - region.offsetX;
    const yPx = lm.y * region.vh - region.offsetY;
    return {
      x: (xPx / region.visibleW) * containerW,
      y: (yPx / region.visibleH) * containerH,
    };
  }

  function pointInOval(pt, cx, cy, rx, ry) {
    const dx = (pt.x - cx) / rx;
    const dy = (pt.y - cy) / ry;
    return dx * dx + dy * dy <= 1.0;
  }

  function faceOvalInsideRatio(landmarks, region, oval) {
    let inside = 0;
    for (let i = 0; i < FACE_OVAL_INDICES.length; i++) {
      const pt = landmarkToContainer(landmarks[FACE_OVAL_INDICES[i]], region, oval.containerW, oval.containerH);
      if (pointInOval(pt, oval.cx, oval.cy, oval.rx, oval.ry)) inside++;
    }
    return inside / FACE_OVAL_INDICES.length;
  }

  function computeOvalGeometry(video) {
    const wrapper = video.parentElement;
    const guide = wrapper && wrapper.querySelector('.face-guide');
    if (!wrapper || !guide) return null;

    const wrapperRect = wrapper.getBoundingClientRect();
    const guideRect = guide.getBoundingClientRect();
    return {
      containerW: wrapperRect.width,
      containerH: wrapperRect.height,
      cx: guideRect.left - wrapperRect.left + guideRect.width / 2,
      cy: guideRect.top - wrapperRect.top + guideRect.height / 2,
      rx: Math.max(1, guideRect.width / 2 + OVAL_EXPAND_PX),
      ry: Math.max(1, guideRect.height / 2 + OVAL_EXPAND_PX),
    };
  }

  function getOvalGeometry(video) {
    if (!cachedOval) cachedOval = computeOvalGeometry(video);
    return cachedOval;
  }

  function invalidateOval() {
    cachedOval = null;
  }

  function computeFaceMetrics(landmarks) {
    let minX = 1, maxX = 0, minY = 1, maxY = 0;
    for (let i = 0; i < landmarks.length; i++) {
      const p = landmarks[i];
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }
    const width = maxX - minX;
    const height = maxY - minY;
    const centerX = minX + width / 2;
    const centerY = minY + height / 2;

    const nose = landmarks[LM.NOSE_TIP];
    const forehead = landmarks[LM.FOREHEAD];
    const chin = landmarks[LM.CHIN];
    const leftEyeOuter = landmarks[LM.LEFT_EYE_OUTER];
    const leftEyeInner = landmarks[LM.LEFT_EYE_INNER];
    const rightEyeInner = landmarks[LM.RIGHT_EYE_INNER];
    const rightEyeOuter = landmarks[LM.RIGHT_EYE_OUTER];
    const leftCheek = landmarks[LM.LEFT_CHEEK];
    const rightCheek = landmarks[LM.RIGHT_CHEEK];

    const leftEyeX = (leftEyeOuter.x + leftEyeInner.x) / 2;
    const leftEyeY = (leftEyeOuter.y + leftEyeInner.y) / 2;
    const rightEyeX = (rightEyeOuter.x + rightEyeInner.x) / 2;
    const rightEyeY = (rightEyeOuter.y + rightEyeInner.y) / 2;
    const eyeMidX = (leftEyeX + rightEyeX) / 2;
    const eyeMidY = (leftEyeY + rightEyeY) / 2;

    const roll = Math.atan2(rightEyeY - leftEyeY, rightEyeX - leftEyeX);

    const leftDist = Math.max(1e-6, nose.x - leftCheek.x);
    const rightDist = Math.max(1e-6, rightCheek.x - nose.x);
    const yaw = (leftDist - rightDist) / (leftDist + rightDist);

    const upper = Math.max(1e-6, nose.y - forehead.y);
    const lower = Math.max(1e-6, chin.y - nose.y);
    const pitch = (upper - lower) / (upper + lower);

    return {
      bbox: { minX, maxX, minY, maxY },
      width,
      height,
      centerX,
      centerY,
      nose,
      eyeMidX,
      eyeMidY,
      yaw,
      pitch,
      roll,
    };
  }

  function analyzeFace(results, video, oval) {
    const faces = results.multiFaceLandmarks || [];

    if (faces.length === 0) return { ok: false, reason: 'Không thấy khuôn mặt' };
    if (faces.length > 1) return { ok: false, reason: 'Chỉ giữ một khuôn mặt trong khung' };

    const landmarks = faces[0];
    const m = computeFaceMetrics(landmarks);

    if (m.width < MIN_FACE_WIDTH) return { ok: false, reason: 'Đưa mặt lại gần hơn' };
    if (m.width > MAX_FACE_WIDTH) return { ok: false, reason: 'Lùi ra xa một chút' };

    const brightness = getBrightness(video);
    if (brightness < MIN_BRIGHTNESS) return { ok: false, reason: 'Tăng ánh sáng mạnh lên' };
    if (brightness > MAX_BRIGHTNESS) return { ok: false, reason: 'Giảm ánh sáng trực tiếp' };

    const region = getVisibleRegion(video, oval.containerW, oval.containerH);
    const insideRatio = faceOvalInsideRatio(landmarks, region, oval);
    if (insideRatio < OVAL_INSIDE_RATIO) {
      return { ok: false, reason: 'Đưa mặt vào trong khung oval' };
    }

    const nosePx = landmarkToContainer(m.nose, region, oval.containerW, oval.containerH);

    return {
      ok: true,
      yaw: m.yaw,
      pitch: m.pitch,
      roll: m.roll,
      nosePx,
    };
  }

  function captureCurrentFrame() {
    const video = el('camera');
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);

    return new Promise((resolve) => {
      canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.95);
    });
  }

  async function completeStep(step) {
    const blob = await captureCurrentFrame();
    if (!blob || !active) return;

    captured.push({ pose: step.pose, blob });
    markStepDone(step.pose);
    stableFrames = 0;
    prevNose = null;
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
    showUiFeedback('Đang lưu ảnh...', '');

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

    const video = el('camera');
    const oval = getOvalGeometry(video);
    if (!oval) return;

    const face = analyzeFace(results, video, oval);
    const step = STEPS[stepIndex];

    if (!face.ok) {
      stableFrames = 0;
      prevNose = null;
      setGuide(false);
      showUiFeedback(face.reason, step.direction);
      return;
    }

    if (!step.passed(face)) {
      stableFrames = 0;
      prevNose = face.nosePx;
      setGuide(false);
      showUiFeedback(step.hint(face), step.direction);
      return;
    }

    if (prevNose) {
      const dx = face.nosePx.x - prevNose.x;
      const dy = face.nosePx.y - prevNose.y;
      if (Math.hypot(dx, dy) > MOTION_PX_LIMIT) {
        stableFrames = 0;
        prevNose = face.nosePx;
        setGuide(true);
        showUiFeedback('Giữ yên...', step.direction);
        return;
      }
    }

    prevNose = face.nosePx;
    stableFrames += 1;
    setGuide(true);

    if (stableFrames >= STABLE_FRAMES_REQUIRED) {
      await completeStep(step);
    } else {
      showUiFeedback('Giữ yên...', step.direction);
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
        showUiFeedback(`Lỗi xử lý camera: ${err.message}`, '');
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
      showUiFeedback('Không tải được FaceMesh', '');
      return;
    }

    stepIndex = 0;
    stableFrames = 0;
    captured = [];
    prevNose = null;
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
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.8,
      minTrackingConfidence: 0.8,
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
        invalidateOval();
        start();
      });
    }
    window.addEventListener('resize', invalidateOval);
    window.addEventListener('orientationchange', invalidateOval);
    start();
  };
}());
