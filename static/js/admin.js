/* ===================================================
   Vinit Mhatre Art - Admin Dashboard JavaScript
   =================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Image preview for artwork creation/editing
  const artworkImgInput = document.getElementById('artwork_image');
  const artworkImgPreview = document.getElementById('artwork_image_preview');

  if (artworkImgInput && artworkImgPreview) {
    artworkImgInput.addEventListener('change', () => {
      if (artworkImgInput.files && artworkImgInput.files[0]) {
        const reader = new FileReader();
        reader.onload = (e) => {
          artworkImgPreview.src = e.target.result;
          artworkImgPreview.style.display = 'block';
        };
        reader.readAsDataURL(artworkImgInput.files[0]);
      }
    });
  }

  // 2. Auto dismiss flash alerts
  setTimeout(() => {
    document.querySelectorAll('.alert').forEach(alert => {
      alert.style.transition = 'opacity 0.4s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 400);
    });
  }, 5000);

  // 3. Confirm Delete Prompts
  document.querySelectorAll('.btn-confirm-delete').forEach(btn => {
    btn.addEventListener('click', (e) => {
      if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
        e.preventDefault();
      }
    });
  });
});
