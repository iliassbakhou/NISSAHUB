// static/js/firebase-auth.js
"use strict";

// Imports from our initialized firebase app
import { 
    auth, 
    onAuthStateChanged, 
    signOut, 
    createUserWithEmailAndPassword, 
    signInWithEmailAndPassword,
    sendPasswordResetEmail // NEW: Import the password reset function
} from './firebase-init.js';

// --- Helper Functions ---
async function createBackendSession(user) {
    if (!user) {
        throw new Error("Firebase user object is null.");
    }
    const idToken = await user.getIdToken();
    const response = await fetch('/auth/session_login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + idToken
        }
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Backend session creation failed.');
    }
    return data;
}

function displayFormMessage(formElement, message, isSuccess = false) {
    // This function can now handle both success and error messages.
    const errorEl = formElement.querySelector('.error-message');
    const successEl = formElement.querySelector('.message');
    
    if (isSuccess) {
        if(successEl) {
            successEl.textContent = message;
            successEl.style.display = 'block';
        }
        if(errorEl) errorEl.style.display = 'none';
    } else {
        if(errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'block';
        }
        if(successEl) successEl.style.display = 'none';
    }
}


function setFormState(formElement, isSubmitting) {
    const button = formElement.querySelector('button[type="submit"]');
    if (button) {
        button.disabled = isSubmitting;
        button.style.opacity = isSubmitting ? 0.7 : 1;
    }
}

// --- Main Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {

    // --- Logout Listener ---
    const logoutLink = document.getElementById('logout-link');
    const mobileLogoutLink = document.getElementById('mobile-logout-link');

    const handleLogout = async (event) => {
        event.preventDefault();
        try {
            await fetch('/auth/session_logout', { method: 'POST' });
            await signOut(auth);
            window.location.href = '/login';
        } catch(error) {
            console.error("Logout failed:", error);
            window.location.href = '/login'; // Force redirect even if there's an error
        }
    };

    if (logoutLink) {
        logoutLink.addEventListener('click', handleLogout);
    }
    if (mobileLogoutLink) {
        mobileLogoutLink.addEventListener('click', handleLogout);
    }


    // --- Login Form Handler ---
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            setFormState(loginForm, true);
            try {
                const email = loginForm.email.value;
                const password = loginForm.password.value;
                const userCredential = await signInWithEmailAndPassword(auth, email, password);
                const sessionResponse = await createBackendSession(userCredential.user);
                window.location.href = sessionResponse.redirect || '/';
            } catch (error) {
                if (error.message.includes('This account has been disabled')) {
                    displayFormMessage(loginForm, 'This account has been disabled. Please contact support.');
                } else {
                    displayFormMessage(loginForm, "Incorrect email or password. Please try again.");
                }
            } finally {
                setFormState(loginForm, false);
            }
        });
    }

    // --- Register Form Handler ---
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (registerForm.password.value !== registerForm['confirm-password'].value) {
                displayFormMessage(registerForm, "Passwords do not match.");
                return;
            }
            
            setFormState(registerForm, true);
            
            try {
                const email = registerForm.email.value;
                const password = registerForm.password.value;
                const userCredential = await createUserWithEmailAndPassword(auth, email, password);
                const sessionResponse = await createBackendSession(userCredential.user);
                window.location.href = sessionResponse.redirect || '/select-role';
            } catch (error) {
                if (error.code === 'auth/email-already-in-use') {
                    displayFormMessage(registerForm, "An account already exists with this email address.");
                } else if (error.code === 'auth/weak-password') {
                    displayFormMessage(registerForm, "Password is too weak. It should be at least 6 characters long.");
                } else {
                    displayFormMessage(registerForm, "An unexpected error occurred during registration.");
                    console.error("Registration Error:", error);
                }
            } finally {
                setFormState(registerForm, false);
            }
        });
    }

    // --- NEW: Forgot Password Form Handler ---
    const forgotPasswordForm = document.getElementById('forgot-password-form');
    if (forgotPasswordForm) {
        forgotPasswordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            setFormState(forgotPasswordForm, true);
            const email = forgotPasswordForm.email.value;

            try {
                await sendPasswordResetEmail(auth, email);
                displayFormMessage(forgotPasswordForm, "Success! If an account exists, a password reset link has been sent to your email.", true);
            } catch (error) {
                // We show a generic success message regardless of outcome to prevent email enumeration attacks
                console.error("Password reset error:", error);
                displayFormMessage(forgotPasswordForm, "Success! If an account exists, a password reset link has been sent to your email.", true);
            } finally {
                setFormState(forgotPasswordForm, false);
            }
        });
    }
});