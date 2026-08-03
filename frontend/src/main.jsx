import "@capacitor/core";
import { Capacitor } from "@capacitor/core";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { ensureApiBase } from "./services/apiBase";
import { initSecureLocalStore } from "./services/secureLocalStore";
import "./app.css";

if (Capacitor.isNativePlatform()) {
  document.body.classList.add("capacitor-native");
  document.body.classList.add(`capacitor-${Capacitor.getPlatform()}`);

  ensureApiBase().catch((error) => {
    console.warn("Backend discovery failed on startup:", error);
  });
} else if (import.meta.env.DEV) {
  ensureApiBase().catch((error) => {
    console.warn("Backend discovery failed on startup:", error);
  });
}

async function bootstrap() {
  try {
    await initSecureLocalStore();
  } catch (error) {
    console.error("Secure local store failed to initialize:", error);
  }

  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </React.StrictMode>
  );
}

bootstrap();

