(function () {
  let recognitionBusy = false;
  let stableRecognition = {
    userId: null,
    count: 0,
  };

  function captureCameraFrame(video) {
    if (!video.videoWidth || !video.videoHeight) return Promise.resolve(null);

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);

    return new Promise((resolve) => {
      canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.9);
    });
  }

  function updateStableRecognition(result) {
    const requiredFrames = 2;

    if (result.status !== 'recognized' || !result.user) {
      stableRecognition = { userId: null, count: 0 };
      const message = result.status === 'reject'
        ? result.message
        : 'Unknown';
      showStatus(message || 'Unknown');
      return;
    }

    if (stableRecognition.userId === result.user.id) {
      stableRecognition.count += 1;
    } else {
      stableRecognition = { userId: result.user.id, count: 1 };
    }

    if (stableRecognition.count >= requiredFrames) {
      showStatus(`✓ Đã nhận diện: ${result.user.name} (${Math.round(result.score * 100)}%)`);
    } else {
      showStatus('Đang xác nhận...');
    }
  }

  window.startBackendRecognition = function startBackendRecognition() {
    const video = document.getElementById('camera');
    if (!video) return;

    const apiUrl = video.dataset.recognitionUrl || '/recognition/api/';
    stableRecognition = { userId: null, count: 0 };
    showStatus('Đang quét khuôn mặt...');

    recognitionInterval = setInterval(async () => {
      if (recognitionBusy || !videoStream) return;

      recognitionBusy = true;
      try {
        const blob = await captureCameraFrame(video);
        if (!blob) {
          showStatus('Đang mở camera...');
          return;
        }

        const formData = new FormData();
        formData.append('image', blob, 'frame.jpg');

        const response = await fetch(apiUrl, {
          method: 'POST',
          body: formData,
        });
        const result = await response.json();
        updateStableRecognition(result);
      } catch (err) {
        stableRecognition = { userId: null, count: 0 };
        showStatus(`Lỗi nhận diện: ${err.message}`);
      } finally {
        recognitionBusy = false;
      }
    }, 1000);
  };
}());
