import "@capacitor/core";
import { Capacitor } from "@capacitor/core";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ensureApiBase } from "./services/apiBase";
import "./app.css";

if (Capacitor.isNativePlatform()) {
  ensureApiBase().catch((error) => {
    console.warn("Backend discovery failed on startup:", error);
  });
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
