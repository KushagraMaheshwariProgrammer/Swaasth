import { useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { canNavigateBack } from "../utils/navigationBack";

export function useNavigateBack(fallback = "/check") {
  const navigate = useNavigate();
  const location = useLocation();

  return useCallback(() => {
    if (canNavigateBack(location)) {
      navigate(-1);
      return;
    }
    navigate(fallback);
  }, [fallback, location, navigate]);
}
