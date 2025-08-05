// static/js/firebase-init.js (Final Corrected Version)
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { 
    getAuth, 
    signInWithEmailAndPassword, 
    onAuthStateChanged, 
    signOut, 
    createUserWithEmailAndPassword, 
    sendPasswordResetEmail
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
// ----- THIS IS THE CORRECTED LINE -----
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";


// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyD0dEUfxPWchaSbRVuKL3UXAPfeQBZJfW0",
    authDomain: "nissahubplatform.firebaseapp.com",
    projectId: "nissahubplatform",
    storageBucket: "nissahubplatform.firebasestorage.app",
    messagingSenderId: "335682506640",
    appId: "1:335682506640:web:0e9b8514240175ff6d6d15",
    measurementId: "G-39CBZGJGYV"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Get a reference to the LIVE services
const auth = getAuth(app);
const db = getFirestore(app);

// Export the services and functions for other scripts to use
export {
    auth,
    db,
    signInWithEmailAndPassword,
    onAuthStateChanged,
    signOut,
    createUserWithEmailAndPassword,
    sendPasswordResetEmail
};