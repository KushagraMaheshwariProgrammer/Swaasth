import { useNavigateBack } from "../hooks/useNavigateBack";

export default function BackLink({
  fallback = "/check",
  className = "back-link",
  children = "← Back",
}) {
  const goBack = useNavigateBack(fallback);

  return (
    <a
      href={fallback}
      className={className}
      onClick={(event) => {
        event.preventDefault();
        goBack();
      }}
    >
      {children}
    </a>
  );
}
