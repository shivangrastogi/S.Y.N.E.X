// config/firebaseConfig.js
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
    apiKey: "AIzaSyCGW8ssB7vKau3Uchx_K0P0Ca52SknLSGo",
    authDomain: "jarvis-remote-6f460.firebaseapp.com",
    databaseURL: "https://jarvis-remote-6f460-default-rtdb.firebaseio.com",
    projectId: "jarvis-remote-6f460",
    storageBucket: "jarvis-remote-6f460.firebasestorage.app",
    messagingSenderId: "674383759043",
    appId: "1:674383759043:web:38cf8b7cad8139958bc476",
    measurementId: "G-BQPENBYK2S"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

export { auth };
