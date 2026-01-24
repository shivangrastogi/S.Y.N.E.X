// screens/ChatScreen.js
import React, { useState, useEffect } from "react";
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator } from "react-native";
import { Ionicons } from "@expo/vector-icons";

export default function ChatScreen() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [jarvisRunning, setJarvisRunning] = useState(false);
  const [listening, setListening] = useState(false);

  const BACKEND_URL = "http://192.168.1.4:5000"; // your Flask IP

  // Fetch logs from backend every 2s
  useEffect(() => {
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, []);

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/get-logs`);
      const data = await res.json();
      setLogs(data.logs || []);
    } catch (err) {
      console.log("Error fetching logs:", err);
    }
  };

  const startJarvis = async () => {
    setLoading(true);
    try {
      await fetch(`${BACKEND_URL}/start-jarvis`, { method: "POST" });
      setJarvisRunning(true);
      setListening(true);
    } catch (err) {
      console.log("Error starting Jarvis:", err);
    }
    setLoading(false);
  };

  const stopJarvis = () => {
    setJarvisRunning(false);
    setListening(false);
  };

  const renderItem = ({ item }) => (
    <View
      style={[
        styles.message,
        item.sender === "User" ? styles.userBubble : styles.jarvisBubble,
      ]}
    >
      <Text style={styles.messageText}>{item.text}</Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.title}>JARVIS Assistant</Text>

      {loading ? (
        <ActivityIndicator size="large" color="#00bcd4" />
      ) : (
        <>
          <FlatList
            data={logs}
            renderItem={renderItem}
            keyExtractor={(_, index) => index.toString()}
            contentContainerStyle={{ paddingBottom: 100 }}
          />

          {listening && (
            <View style={styles.listeningContainer}>
              <Ionicons
                name="mic"
                size={36}
                color="#ff3b30"
                style={{ marginBottom: 6 }}
              />
              <Text style={styles.listeningText}>Listening…</Text>
            </View>
          )}

          <View style={styles.buttonsContainer}>
            {!jarvisRunning ? (
              <TouchableOpacity style={styles.buttonStart} onPress={startJarvis}>
                <Ionicons name="play-circle" size={32} color="#fff" />
                <Text style={styles.buttonText}>Start Jarvis</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity style={styles.buttonStop} onPress={stopJarvis}>
                <Ionicons name="stop-circle" size={32} color="#fff" />
                <Text style={styles.buttonText}>Stop Jarvis</Text>
              </TouchableOpacity>
            )}
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a", padding: 16 },
  title: {
    fontSize: 22,
    fontWeight: "bold",
    color: "#00e5ff",
    textAlign: "center",
    marginVertical: 10,
  },
  message: {
    marginVertical: 6,
    padding: 10,
    borderRadius: 12,
    maxWidth: "80%",
  },
  userBubble: {
    backgroundColor: "#1e88e5",
    alignSelf: "flex-end",
  },
  jarvisBubble: {
    backgroundColor: "#212121",
    alignSelf: "flex-start",
  },
  messageText: { color: "#fff", fontSize: 16 },
  buttonsContainer: {
    position: "absolute",
    bottom: 30,
    alignSelf: "center",
    flexDirection: "row",
    gap: 20,
  },
  buttonStart: {
    backgroundColor: "#00c853",
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: 30,
  },
  buttonStop: {
    backgroundColor: "#d50000",
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: 30,
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
    marginLeft: 8,
  },
  listeningContainer: {
    position: "absolute",
    bottom: 100,
    alignSelf: "center",
    alignItems: "center",
  },
  listeningText: {
    color: "#ff3b30",
    fontSize: 16,
    fontWeight: "500",
  },
});
