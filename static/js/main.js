/* ===================================================
   Vinit Mhatre Art - Main Customer JavaScript
   Interactive controls, dynamic pricing, file preview
   =================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Menu Toggle
  const menuToggle = document.getElementById('menuToggle');
  const mainNav = document.getElementById('mainNav');

  if (menuToggle && mainNav) {
    menuToggle.addEventListener('click', () => {
      const isOpen = mainNav.classList.toggle('open');
      menuToggle.setAttribute('aria-expanded', String(isOpen));
      menuToggle.textContent = isOpen ? '✕' : '☰';
    });

    mainNav.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        mainNav.classList.remove('open');
        menuToggle.setAttribute('aria-expanded', 'false');
        menuToggle.textContent = '☰';
      });
    });
  }

  // 2. Auto-dismiss Flash Alerts
  document.querySelectorAll('.alert-close').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const alert = e.target.closest('.alert');
      if (alert) alert.remove();
    });
  });

  setTimeout(() => {
    document.querySelectorAll('.alert').forEach(alert => {
      alert.style.transition = 'opacity 0.4s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 400);
    });
  }, 6000);

  // 3. Dynamic Price Estimator for Custom Order Form
  const orderForm = document.getElementById('customOrderForm');
  if (orderForm) {
    const categorySelect = document.getElementById('category');
    const sizeSelect = document.getElementById('size_canvas');
    const facesGroup = document.getElementById('facesGroup');
    const facesSelect = document.getElementById('num_faces');
    const framingSelect = document.getElementById('framing');
    const estimatePriceDisplay = document.getElementById('estimatePriceDisplay');
    const estimateBreakdown = document.getElementById('estimateBreakdown');
    const hiddenEstimatedInput = document.getElementById('hiddenEstimatedPrice');

    const pricingRules = {
      'Pencil Portraits': {
        base: {
          'A5 (Miniature - 5.8 x 8.3 in)': 899,
          'A4 (Standard - 8.3 x 11.7 in)': 1499,
          'A3 (Medium - 11.7 x 16.5 in)': 2499,
          'A2 (Large - 16.5 x 23.4 in)': 3999,
          'Custom Size': 2200
        },
        hasFaces: true
      },
      'Colour Drawings': {
        base: {
          'A5 (Miniature - 5.8 x 8.3 in)': 1099,
          'A4 (Standard - 8.3 x 11.7 in)': 1999,
          'A3 (Medium - 11.7 x 16.5 in)': 2999,
          'A2 (Large - 16.5 x 23.4 in)': 4699,
          'Custom Size': 2800
        },
        hasFaces: true
      },
      'Rangoli': {
        base: {
          '4 ft x 4 ft (Intimate)': 2499,
          '6 ft x 6 ft (Grand)': 3500,
          '8 ft x 8 ft (Festive/Wedding)': 5200,
          'Custom Size': 3500
        },
        hasFaces: false
      },
      'Watercolour Paintings': {
        base: {
          'A5 (Miniature - 5.8 x 8.3 in)': 999,
          'A4 (Standard - 8.3 x 11.7 in)': 1899,
          'A3 (Medium - 11.7 x 16.5 in)': 2899,
          'A2 (Large - 16.5 x 23.4 in)': 4299,
          'Custom Size': 2600
        },
        hasFaces: true
      },
      'Fabric Painting': {
        base: {
          'Small Item (T-Shirt/Tote/Cushion)': 1500,
          'Medium Item (Dupatta / Stole)': 3200,
          'Large Item (Saree / Full Fabric)': 5500,
          'Custom Size': 3000
        },
        hasFaces: false
      },
      'Decorative Art': {
        base: {
          '12 x 12 inches Canvas': 1800,
          '16 x 16 inches Canvas': 3200,
          '24 x 24 inches Canvas': 4900,
          'Custom Size': 3200
        },
        hasFaces: false
      },
      'Other Custom Artwork': {
        base: {
          'Small Scale': 1499,
          'Standard Size': 2499,
          'Large Scale': 4499,
          'Custom Size': 2499
        },
        hasFaces: false
      }
    };

    function updateSizeOptions() {
      const category = categorySelect.value;
      const currentSize = sizeSelect.value;
      sizeSelect.innerHTML = '<option value="">-- Choose Size / Dimensions --</option>';

      if (pricingRules[category]) {
        const sizes = Object.keys(pricingRules[category].base);
        sizes.forEach(sz => {
          const opt = document.createElement('option');
          opt.value = sz;
          opt.textContent = `${sz} (From ₹${pricingRules[category].base[sz].toLocaleString('en-IN')})`;
          if (sz === currentSize) opt.selected = true;
          sizeSelect.appendChild(opt);
        });

        // Toggle faces group visibility
        if (facesGroup) {
          if (pricingRules[category].hasFaces) {
            facesGroup.style.display = 'block';
          } else {
            facesGroup.style.display = 'none';
          }
        }
      }
      recalculatePrice();
    }

    function recalculatePrice() {
      const category = categorySelect.value;
      const size = sizeSelect.value;
      const faces = facesSelect ? parseInt(facesSelect.value || 1, 10) : 1;
      const framing = framingSelect ? framingSelect.value : 'Unframed / Rolled';

      let basePrice = 1499;
      let faceAddon = 0;
      let frameAddon = 0;

      if (pricingRules[category] && pricingRules[category].base[size]) {
        basePrice = pricingRules[category].base[size];
      }

      if (pricingRules[category] && pricingRules[category].hasFaces) {
        if (faces === 2) faceAddon = 600;
        else if (faces === 3) faceAddon = 1200;
        else if (faces >= 4) faceAddon = 1800;
      }

      if (framing === 'Classic Wooden Frame') {
        frameAddon = 650;
      } else if (framing === 'Premium Black Acrylic Frame') {
        frameAddon = 1100;
      }

      const total = basePrice + faceAddon + frameAddon;

      if (estimatePriceDisplay) {
        estimatePriceDisplay.textContent = `₹${total.toLocaleString('en-IN')}`;
      }
      if (hiddenEstimatedInput) {
        hiddenEstimatedInput.value = total;
      }

      if (estimateBreakdown) {
        estimateBreakdown.innerHTML = `
          <li><span>Base Size Rate (${category || 'Art'}):</span> <b>₹${basePrice.toLocaleString('en-IN')}</b></li>
          ${faceAddon > 0 ? `<li><span>Additional Subject(s) (${faces} Faces):</span> <b>+₹${faceAddon.toLocaleString('en-IN')}</b></li>` : ''}
          ${frameAddon > 0 ? `<li><span>${framing}:</span> <b>+₹${frameAddon.toLocaleString('en-IN')}</b></li>` : ''}
          <li style="font-weight:700; color:var(--text-dark); border-top:1px solid var(--border-subtle); padding-top:12px;">
            <span>Estimated Total:</span> <b style="color:var(--accent-terracotta);">₹${total.toLocaleString('en-IN')}</b>
          </li>
        `;
      }
    }

    categorySelect.addEventListener('change', updateSizeOptions);
    sizeSelect.addEventListener('change', recalculatePrice);
    if (facesSelect) facesSelect.addEventListener('change', recalculatePrice);
    if (framingSelect) framingSelect.addEventListener('change', recalculatePrice);

    // Initial run
    if (categorySelect.value) {
      updateSizeOptions();
    }
  }

  // 4. Reference Image File Drag-and-Drop & Preview
  const uploadZone = document.getElementById('uploadZone');
  const fileInput = document.getElementById('reference_photo');
  const previewContainer = document.getElementById('uploadPreviewContainer');
  const previewImg = document.getElementById('uploadPreviewImg');
  const removeUploadBtn = document.getElementById('removeUploadBtn');

  if (uploadZone && fileInput) {
    ['dragenter', 'dragover'].forEach(eventName => {
      uploadZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      uploadZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
      }, false);
    });

    uploadZone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files.length > 0) {
        fileInput.files = files;
        showPreview(files[0]);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files[0]) {
        showPreview(fileInput.files[0]);
      }
    });

    if (removeUploadBtn) {
      removeUploadBtn.addEventListener('click', (e) => {
        e.preventDefault();
        fileInput.value = '';
        if (previewContainer) previewContainer.style.display = 'none';
        uploadZone.style.display = 'block';
      });
    }

    function showPreview(file) {
      if (!file.type.match('image.*')) {
        alert('Please upload an image file (PNG, JPG, or WEBP).');
        fileInput.value = '';
        return;
      }
      if (file.size > 16 * 1024 * 1024) {
        alert('File size exceeds 16MB. Please choose a smaller photo.');
        fileInput.value = '';
        return;
      }

      const reader = new FileReader();
      reader.onload = (e) => {
        if (previewImg && previewContainer) {
          previewImg.src = e.target.result;
          previewContainer.style.display = 'block';
          uploadZone.style.display = 'none';
        }
      };
      reader.readAsDataURL(file);
    }
  }

  // 5. Copy Order ID Button
  const copyBtn = document.getElementById('copyOrderIdBtn');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const code = copyBtn.getAttribute('data-code');
      navigator.clipboard.writeText(code).then(() => {
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = '✓ Copied!';
        setTimeout(() => {
          copyBtn.innerHTML = originalText;
        }, 2000);
      });
    });
  }
});
