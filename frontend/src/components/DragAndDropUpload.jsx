import { useCallback, useRef, useState } from "react";
import DocumentFilePreview from "./DocumentFilePreview";
import { DEFAULT_FILE_ACCEPT, validateUploadFile } from "../utils/fileUpload";

export default function DragAndDropUpload({
  icon = "↑",
  title = "Drop your file here or click to browse",
  dragTitle = "Drop your file here",
  subtitle = "Supports PDF, JPG, PNG",
  accept = DEFAULT_FILE_ACCEPT,
  file = null,
  onFileSelect,
  onValidationError,
  className = "",
  disabled = false,
}) {
  const inputRef = useRef(null);
  const dragCounterRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);
  const processFile = useCallback(
    (selectedFile) => {
      if (!selectedFile) {
        return;
      }
      const result = validateUploadFile(selectedFile);
      if (!result.ok) {
        onValidationError?.(result.error);
        onFileSelect?.(null);
        return;
      }
      onValidationError?.("");
      onFileSelect?.(selectedFile);
    },
    [onFileSelect, onValidationError]
  );

  const handleDragEnter = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (disabled) {
      return;
    }
    dragCounterRef.current += 1;
    setIsDragging(true);
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (disabled) {
      return;
    }
    dragCounterRef.current -= 1;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragging(false);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragging(false);
    if (disabled) {
      return;
    }
    processFile(event.dataTransfer.files?.[0]);
  };

  const handleClick = () => {
    if (!disabled) {
      inputRef.current?.click();
    }
  };

  const handleInputChange = (event) => {
    processFile(event.target.files?.[0]);
    event.target.value = "";
  };

  return (
    <>
      <button
        type="button"
        className={`upload-zone ${isDragging ? "upload-zone-dragging" : ""} ${className}`.trim()}
        onClick={handleClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        disabled={disabled}
        aria-label={title}
      >
        {file ? (
          <DocumentFilePreview file={file} className="upload-preview" />
        ) : (
          <div className="upload-icon">{icon}</div>
        )}
        <p className="upload-title">{isDragging ? dragTitle : title}</p>
        <p className="upload-subtitle">{subtitle}</p>
        {file && <p className="file-name">{file.name}</p>}
      </button>
      <input
        ref={inputRef}
        className="hidden-input"
        type="file"
        accept={accept}
        onChange={handleInputChange}
        disabled={disabled}
      />
    </>
  );
}
