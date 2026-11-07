// Scan page: webcam capture -> /predict (YOLO boxes) -> /confirm (AI extraction) -> edit.html.

const cameraElement = document.getElementById('camera');
const captureBtn = document.getElementById('captureBtn');
const confirmBtn = document.getElementById('confirmBtn');
const logoutBtn = document.getElementById('logoutBtn');
const outputImage = document.getElementById('outputImage');

function cameraErrorMessage(error) {
    switch (error && error.name) {
        case 'NotAllowedError':
            return 'Camera access was blocked. Allow camera access for this site in your browser settings, then reload.';
        case 'NotFoundError':
        case 'OverconstrainedError':
            return 'No camera was found. Connect a webcam and reload the page.';
        case 'NotReadableError':
            return 'The camera is being used by another app. Close it and reload the page.';
        default:
            return "Couldn't start the camera. Reload the page to try again.";
    }
}

async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showMessage('This browser cannot use the camera here. Use a recent Chrome, Safari or Firefox, and open the app at http://127.0.0.1:5500.');
        captureBtn.disabled = true;
        return;
    }
    try {
        // Prefer the rear camera on phones; laptops fall back to the webcam.
        cameraElement.srcObject = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    } catch (error) {
        console.error('Camera error:', error);
        showMessage(cameraErrorMessage(error));
        captureBtn.disabled = true;
    }
}

function captureFrame() {
    if (!cameraElement.videoWidth) return null;
    const canvas = document.createElement('canvas');
    canvas.width = cameraElement.videoWidth;
    canvas.height = cameraElement.videoHeight;
    canvas.getContext('2d').drawImage(cameraElement, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.9);
}

captureBtn.addEventListener('click', async () => {
    const image = captureFrame();
    if (!image) {
        showMessage("The camera isn't ready yet. Wait a moment and try again.");
        return;
    }
    confirmBtn.hidden = true;
    showMessage('Looking for business cards…', 'info');
    try {
        const data = await whileBusy(captureBtn, 'Scanning…', () =>
            api('/predict', { method: 'POST', body: { image } }));
        outputImage.src = data.image_with_bboxes;
        outputImage.hidden = false;
        if (data.count === 0) {
            showMessage('No business cards found. Hold the card flat, fill more of the frame, use good light, and try again.');
            return;
        }
        const plural = data.count === 1 ? 'card' : 'cards';
        showMessage(`Found ${data.count} ${plural}. Check the boxes, then press Confirm to read them.`, 'success');
        confirmBtn.hidden = false;
    } catch (error) {
        showMessage(errorText(error));
    }
});

confirmBtn.addEventListener('click', async () => {
    showMessage('Reading the cards with AI. This can take a few seconds…', 'info');
    try {
        const data = await whileBusy(confirmBtn, 'Reading…', () => api('/confirm', { method: 'POST' }));
        if (!data.crops || data.crops.length === 0) {
            showMessage('No readable cards in that scan. Capture a new image and try again.');
            confirmBtn.hidden = true;
            return;
        }
        window.location.href = 'edit.html';
    } catch (error) {
        confirmBtn.hidden = true;  // the scan is used up; a new capture is needed
        showMessage(errorText(error) + ' Capture a new image to try again.');
    }
});

logoutBtn.addEventListener('click', async () => {
    try {
        await api('/logout', { method: 'POST' });
    } catch (error) {
        console.error('Logout error:', error);  // still leave the page; the session is cleared or already gone
    }
    window.top.location.href = 'login.html';
});

window.addEventListener('load', startCamera);
