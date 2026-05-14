/**
 * Face Recognition Demo - Main JavaScript
 * Chứa các hàm dùng chung cho camera và xử lý ảnh
 */

let videoStream = null;
let recognitionInterval = null;

/**
 * Khởi tạo camera và hiển thị lên video element
 * @param {string} elementId - ID của thẻ video
 */
async function initCamera(elementId) {
  const video = document.getElementById(elementId);

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    const insecure = location.protocol !== 'https:' && !isLocal;
    const msg = insecure
      ? 'Camera yêu cầu HTTPS trên iPhone/Safari. Hãy mở trang qua HTTPS (ngrok/cloudflared/runserver_plus).'
      : 'Trình duyệt không hỗ trợ camera.';
    showStatus(msg);
    throw new Error(msg);
  }

  try {
    videoStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 }
    });
    video.srcObject = videoStream;
    video.setAttribute('playsinline', '');
    video.setAttribute('muted', '');
    video.muted = true;
    try { await video.play(); } catch (_) { /* iOS may need user gesture */ }
  } catch (err) {
    const reason = err && err.name === 'NotAllowedError'
      ? 'Bạn đã từ chối quyền camera. Vào Settings → Safari → Camera để cấp lại.'
      : `Không thể truy cập camera: ${err.message || err.name}`;
    showStatus(reason);
    throw err;
  }
}

/**
 * Dừng camera và giải phóng tài nguyên
 */
function stopCamera() {
  if (videoStream) {
    videoStream.getTracks().forEach(track => track.stop());
    videoStream = null;
  }
  if (recognitionInterval) {
    clearInterval(recognitionInterval);
    recognitionInterval = null;
  }
  showStatus('Đã dừng camera');
}

/**
 * Chụp ảnh từ camera để đăng ký khuôn mặt
 */
function capturePhoto() {
  const video = document.getElementById('camera');
  const canvas = document.createElement('canvas');
  
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  
  const imageData = canvas.toDataURL('image/jpeg');
  
  // Demo: Lưu ảnh vào localStorage
  const faces = JSON.parse(localStorage.getItem('faces') || '[]');
  faces.push({ id: Date.now(), image: imageData });
  localStorage.setItem('faces', JSON.stringify(faces));
  
  showStatus('✓ Đã đăng ký khuôn mặt thành công!');
  stopCamera();
}

/** Lưu trữ tạm các ảnh đã upload */
let uploadedImages = [];

/**
 * Xem trước nhiều ảnh được upload
 * @param {Event} event - Event từ input file
 */
function previewImage(event) {
  const files = event.target.files;
  const btn = document.getElementById('register-btn');

  if (!files.length) {
    if (btn) btn.disabled = true;
    return;
  }

  const count = files.length;
  const valid = count >= 2 && count <= 5;
  if (btn) btn.style.display = valid ? 'flex' : 'none';

  const statusEl = document.getElementById('status');
  if (statusEl) {
    if (count < 2) {
      statusEl.textContent = `Vui lòng chọn ít nhất 2 ảnh (đang chọn ${count})`;
      statusEl.style.display = 'block';
    } else if (count > 5) {
      statusEl.textContent = `Tối đa 5 ảnh (đang chọn ${count})`;
      statusEl.style.display = 'block';
    } else {
      statusEl.style.display = 'none';
    }
  }

  const icon = document.getElementById('upload-icon');
  const text = document.getElementById('upload-text');
  const preview = document.getElementById('preview');
  
  // Ẩn icon và text mặc định
  icon.style.display = 'none';
  text.style.display = 'none';
  preview.style.display = 'none';
  
  // Tạo container chứa preview nếu chưa có
  let previewContainer = document.getElementById('preview-container');
  if (!previewContainer) {
    previewContainer = document.createElement('div');
    previewContainer.id = 'preview-container';
    previewContainer.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;justify-content:center;';
    preview.parentNode.appendChild(previewContainer);
  }
  previewContainer.innerHTML = '';
  uploadedImages = [];
  
  // Đọc từng file và tạo preview
  Array.from(files).forEach(file => {
    const reader = new FileReader();
    reader.onload = function(e) {
      uploadedImages.push(e.target.result);
      
      const img = document.createElement('img');
      img.src = e.target.result;
      img.style.cssText = 'width:80px;height:80px;object-fit:cover;border-radius:8px;';
      previewContainer.appendChild(img);
    };
    reader.readAsDataURL(file);
  });
}

/**
 * Đăng ký khuôn mặt từ các ảnh đã upload
 */
function registerUploadedPhoto() {
  if (!uploadedImages.length) {
    showStatus('Vui lòng chọn ảnh trước');
    return;
  }
  
  // Demo: Lưu tất cả ảnh vào localStorage
  const faces = JSON.parse(localStorage.getItem('faces') || '[]');
  uploadedImages.forEach(img => {
    faces.push({ id: Date.now() + Math.random(), image: img });
  });
  localStorage.setItem('faces', JSON.stringify(faces));
  
  showStatus('✓ Đã đăng ký ' + uploadedImages.length + ' khuôn mặt!');
  uploadedImages = [];
}

/**
 * Bắt đầu quá trình nhận diện khuôn mặt
 * Demo: Giả lập việc quét mỗi 2 giây
 */
function startRecognition() {
  const faces = JSON.parse(localStorage.getItem('faces') || '[]');
  
  if (faces.length === 0) {
    showStatus('Chưa có khuôn mặt nào được đăng ký');
    return;
  }
  
  let scanCount = 0;
  
  recognitionInterval = setInterval(() => {
    scanCount++;
    
    // Demo: Random kết quả nhận diện
    if (scanCount % 3 === 0 && faces.length > 0) {
      showStatus('✓ Đã nhận diện: User #' + faces[0].id);
    } else {
      showStatus('Đang quét khuôn mặt...');
    }
  }, 2000);
}

/**
 * Hiển thị thông báo trạng thái
 * @param {string} message - Nội dung thông báo
 */
function showStatus(message) {
  const status = document.getElementById('status');
  if (status) {
    status.textContent = message;
    status.style.display = 'block';
  }
}

/**
 * Bật/tắt menu dropdown
 */
function toggleMenu() {
  const menu = document.getElementById('menu');
  menu.classList.toggle('show');
}

// Đóng menu khi click ra ngoài
document.addEventListener('click', function(e) {
  const menu = document.getElementById('menu');
  const btn = document.querySelector('.menu-btn');
  if (menu && btn && !menu.contains(e.target) && !btn.contains(e.target)) {
    menu.classList.remove('show');
  }
});
