import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";
import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { canNavigateBack } from "../utils/navigationBack";

const EXIT_PATHS = new Set(["/", "/login", "/verify-email", "/check"]);

export function useAndroidBackButton() {
  const navigate = useNavigate();
  const location = useLocation();
  const locationRef = useRef(location);

  locationRef.current = location;

  useEffect(() => {
    if (!Capacitor.isNativePlatform() || Capacitor.getPlatform() !== "android") {
      return undefined;
    }

    let removed = false;
    let listenerHandle;

    App.addListener("backButton", () => {
      const current = locationRef.current;

      if (canNavigateBack(current)) {
        navigate(-1);
        return;
      }

      if (EXIT_PATHS.has(current.pathname)) {
        App.exitApp();
        return;
      }

      navigate("/check", { replace: true });
    }).then((handle) => {
      if (removed) {
        handle.remove();
        return;
      }
      listenerHandle = handle;
    });

    return () => {
      removed = true;
      listenerHandle?.remove();
    };
  }, [navigate]);
}
