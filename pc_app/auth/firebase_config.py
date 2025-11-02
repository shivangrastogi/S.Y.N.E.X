import pyrebase4 as pyrebase

firebaseConfig = {
    "apiKey": "AIzaSyCGW8ssB7vKau3Uchx_K0P0Ca52SknLSGo",
    "authDomain": "jarvis-remote-6f460.firebaseapp.com",
    "databaseURL": "https://jarvis-remote-6f460-default-rtdb.firebaseio.com",
    "projectId": "jarvis-remote-6f460",
    "storageBucket": "jarvis-remote-6f460.firebasestorage.app",
    "messagingSenderId": "674383759043",
    "appId": "1:674383759043:web:38cf8b7cad8139958bc476",
    "measurementId": "G-BQPENBYK2S"
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db = firebase.database()
