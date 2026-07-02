import { useEffect, useState } from "react";
import { isImageFile, isPdfFile } from "../utils/fileUpload";

export function useFilePreviewUrl(file) {
  const [previewUrl, setPreviewUrl] = useState(null);

  useEffect(() => {
    if (!file || (!isImageFile(file) && !isPdfFile(file))) {
      setPreviewUrl(null);
      return undefined;
    }

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return previewUrl;
}

export default function DocumentFilePreview({
  file,
  className = "",
  clickable = false,
  onClick,
  ariaLabel,
}) {
  const previewUrl = useFilePreviewUrl(file);

  if (!file || !previewUrl) {
    return null;
  }

  const rootClassName = [
    "document-file-preview",
    clickable ? "document-file-preview-clickable" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const handleClick = () => {
    if (clickable && onClick) {
      onClick();
    }
  };

  const handleKeyDown = (event) => {
    if (!clickable || !onClick) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onClick();
    }
  };

  const interactiveProps = clickable
    ? {
        role: "button",
        tabIndex: 0,
        onClick: handleClick,
        onKeyDown: handleKeyDown,
        "aria-label": ariaLabel || `Preview of ${file.name}`,
      }
    : {};

  if (isImageFile(file)) {
    return (
      <div className={rootClassName} {...interactiveProps}>
        <img
          src={previewUrl}
          alt={`Preview of ${file.name}`}
          className="document-file-preview-image"
          draggable={false}
        />
        {clickable && <span className="document-file-preview-hint">Tap to review</span>}
      </div>
    );
  }

  if (isPdfFile(file)) {
    return (
      <div
        className={`${rootClassName} document-file-preview-pdf`.trim()}
        {...interactiveProps}
      >
        <iframe
          src={previewUrl}
          title={`Preview of ${file.name}`}
          className="document-file-preview-iframe"
          tabIndex={-1}
        />
        {clickable && <span className="document-file-preview-hint">Tap to review</span>}
      </div>
    );
  }

  return null;
}
