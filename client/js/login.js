// Login and sign-up page.

const form = document.getElementById('login-form');
const loginButton = document.getElementById('login-btn');
const signupButton = document.getElementById('signup-btn');

function credentials() {
    return {
        email: document.getElementById('email').value.trim().toLowerCase(),
        password: document.getElementById('password').value,
    };
}

function checkFilledIn({ email, password }) {
    if (!email || !password) {
        showMessage('Enter your email and password.');
        return false;
    }
    return true;
}

async function login() {
    const body = credentials();
    if (!checkFilledIn(body)) return;
    try {
        await whileBusy(loginButton, 'Logging in…', () =>
            api('/login_authorization', { method: 'POST', body, redirectOn401: false }));
        window.location.href = 'index.html';
    } catch (error) {
        showMessage(errorText(error));
    }
}

async function signup() {
    const body = credentials();
    if (!checkFilledIn(body)) return;
    try {
        await whileBusy(signupButton, 'Creating account…', () =>
            api('/signup_authorization', { method: 'POST', body, redirectOn401: false }));
        showMessage('Account created. You can now log in.', 'success');
    } catch (error) {
        showMessage(errorText(error));
    }
}

// Enter in either field logs in.
form.addEventListener('submit', event => {
    event.preventDefault();
    login();
});
signupButton.addEventListener('click', signup);
