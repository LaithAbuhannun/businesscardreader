// Scan page: photo -> /predict (YOLO boxes) -> /confirm (AI extraction) -> edit.html.
//
// Two ways to get a photo:
//  - the live camera (needs localhost or HTTPS; see "python server.py --phone")
//  - "Take or choose photo", which opens the phone's own camera or photo library
//    and works everywhere, even over plain HTTP.

const cameraBox = document.getElementById('cameraBox');
const cameraElement = document.getElementById('camera');
const captureBtn = document.getElementById('captureBtn');
const photoInput = document.getElementById('photoInput');
const confirmBtn = document.getElementById('confirmBtn');
const outputImage = document.getElementById('outputImage');

// Phone photos are often 12+ megapixels. The model works at 1024 px, so
// shrinking first makes uploads fast on mobile data and keeps under the 10 MB limit.
const MAX_SIDE = 2048;

function cameraErrorMessage(error) {
    switch (error && error.name) {
        case 'NotAllowedError':
            return 'Camera access was blocked. Allow it in your browser settings, or use "Take or choose photo".';
        case 'NotFoundError':
        case 'OverconstrainedError':
            return 'No camera was found. Use "Take or choose photo" instead.';
        case 'NotReadableError':
            return 'The camera is being used by another app. Close it and reload, or use "Take or choose photo".';
        default:
            return 'Couldn\'t start the camera. Use "Take or choose photo" instead.';
    }
}

function useLiveCamera(available) {
    cameraBox.hidden = !available;
    captureBtn.hidden = !available;
}

async function startCamera() {
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        // Browsers only allow the live camera on localhost or HTTPS.
        useLiveCamera(false);
        showMessage('Tap "Take or choose photo" to scan a card.', 'info');
        return;
    }
    try {
        // Prefer the rear camera on phones; laptops fall back to the webcam.
        cameraElement.srcObject = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
            audio: false,
        });
        useLiveCamera(true);
    } catch (error) {
        console.error('Camera error:', error);
        useLiveCamera(false);
        showMessage(cameraErrorMessage(error));
    }
}

// Draws an image or video frame to a canvas, scaled so its longest side is at most MAX_SIDE.
function toJpegDataUrl(source, width, height) {
    const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    canvas.getContext('2d').drawImage(source, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.9);
}

function loadImage(file) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
        img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('unreadable image')); };
        img.src = url;
    });
}

async function scan(image, button, busyLabel) {
    confirmBtn.hidden = true;
    showMessage('Looking for business cards…', 'info');
    try {
        const data = await whileBusy(button, busyLabel, () => api('/predict', { method: 'POST', body: { image } }));
        outputImage.src = data.image_with_bboxes;
        outputImage.hidden = false;
        if (data.count === 0) {
            showMessage('No business cards found. Hold the card flat, fill more of the frame, use good light, and try again.');
            return;
        }
        const plural = data.count === 1 ? 'card' : 'cards';
        showMessage(`Found ${data.count} ${plural}. Check the boxes, then tap Confirm to read them.`, 'success');
        confirmBtn.hidden = false;
        confirmBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (error) {
        showMessage(errorText(error));
    }
}

captureBtn.addEventListener('click', () => {
    if (!cameraElement.videoWidth) {
        showMessage("The camera isn't ready yet. Wait a moment and try again.");
        return;
    }
    const image = toJpegDataUrl(cameraElement, cameraElement.videoWidth, cameraElement.videoHeight);
    scan(image, captureBtn, 'Scanning…');
});

photoInput.addEventListener('change', async () => {
    const file = photoInput.files && photoInput.files[0];
    photoInput.value = '';  // lets the same photo be picked again
    if (!file) return;
    let image;
    try {
        const img = await loadImage(file);
        image = toJpegDataUrl(img, img.naturalWidth, img.naturalHeight);
    } catch (error) {
        console.error('Photo error:', error);
        showMessage("Couldn't open that photo. Try a JPEG or PNG, or take a new photo.");
        return;
    }
    scan(image, captureBtn, 'Scanning…');
});

confirmBtn.addEventListener('click', async () => {
    showMessage('Reading the cards with AI. This can take a few seconds…', 'info');
    try {
        const data = await whileBusy(confirmBtn, 'Reading…', () => api('/confirm', { method: 'POST' }));
        if (!data.crops || data.crops.length === 0) {
            showMessage('No readable cards in that scan. Take a new photo and try again.');
            confirmBtn.hidden = true;
            return;
        }
        window.location.href = 'edit.html';
    } catch (error) {
        confirmBtn.hidden = true;  // the scan is used up; a new photo is needed
        showMessage(errorText(error) + ' Take a new photo to try again.');
    }
});

window.addEventListener('load', startCamera);
