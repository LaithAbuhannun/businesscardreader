// Shared helpers for every page: one way to call the API, one way to show messages.
//
// Card text comes from an AI model reading a photo, so it is always inserted
// as text (textContent), never as HTML, to prevent script injection.

const CARD_FIELDS = [
    ['name', 'Name'],
    ['company_name', 'Company Name'],
    ['phone_number', 'Phone Number'],
    ['email', 'Email'],
];

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

// Calls the backend and returns the parsed JSON.
// Throws ApiError with a message that is safe to show to the user.
// A 401 (logged out or session expired) sends the user to the login page,
// unless redirectOn401 is false (the login page itself).
async function api(path, { method = 'GET', body, redirectOn401 = true, raw = false } = {}) {
    const options = { method, credentials: 'same-origin', headers: {} };
    // The server requires JSON on every change (it blocks cross-site forms),
    // so changes always send a JSON body, even an empty one.
    if (method !== 'GET') {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body === undefined ? {} : body);
    }

    let response;
    try {
        response = await fetch(path, options);
    } catch (networkError) {
        console.error(`Network error calling ${path}:`, networkError);
        throw new ApiError("Can't reach the server. Check that it is running and try again.", 0);
    }

    if (response.status === 401 && redirectOn401) {
        window.top.location.href = 'login.html';
        throw new ApiError('Your session has ended. Please log in again.', 401);
    }

    if (raw && response.ok) return response;

    let data = null;
    try {
        data = await response.json();
    } catch (parseError) {
        // Not JSON (for example a proxy error page). Fall through to the status message.
    }

    if (!response.ok || (data && data.success === false)) {
        const fallback = {
            413: 'That image is too large. Try a smaller photo.',
            429: 'Too many attempts. Please wait a minute and try again.',
            500: 'Something went wrong on the server. Please try again.',
        }[response.status] || `Request failed (error ${response.status}).`;
        const message = data && typeof data.error === 'string' ? data.error : fallback;
        console.error(`${method} ${path} failed:`, response.status, message);
        throw new ApiError(message, response.status);
    }
    return data;
}

// Shows a message in the page's #message box (created if missing).
// kind is 'error', 'success' or 'info'. Pass an empty text to hide it.
function showMessage(text, kind = 'error') {
    let box = document.getElementById('message');
    if (!box) {
        box = document.createElement('div');
        box.id = 'message';
        document.body.prepend(box);
    }
    box.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    box.className = `message message-${kind}`;
    box.textContent = text;
    box.hidden = !text;
}

function errorText(error) {
    return error instanceof ApiError ? error.message : 'Something unexpected went wrong. Please try again.';
}

// Disables a button while an async task runs, so it can't be double-clicked.
async function whileBusy(button, busyLabel, task) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = busyLabel;
    try {
        return await task();
    } finally {
        button.disabled = false;
        button.textContent = label;
    }
}

function cardImage(src) {
    const img = document.createElement('img');
    img.alt = 'Business card';
    if (typeof src === 'string' && src.startsWith('data:image/')) img.src = src;
    return img;
}
