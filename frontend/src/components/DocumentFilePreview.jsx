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

export default function DocumentFilePreview({ file, className = "" }) {
  const previewUrl = useFilePreviewUrl(file);

  if (!file || !previewUrl) {
    return null;
  }

  const rootClassName = `document-file-preview ${className}`.trim();

  if (isImageFile(file)) {
    return (
      <div className={rootClassName}>
        <img
          src={previewUrl}
          alt={`Preview of ${file.name}`}
          className="document-file-preview-image"
        />
      </div>
    );
  }

  if (isPdfFile(file)) {
    return (
      <div className={`${rootClassName} document-file-preview-pdf`.trim()}>
        <iframe
          src={previewUrl}
          title={`Preview of ${file.name}`}
          className="document-file-preview-iframe"
        />
      </div>
    );
  }

  return null;
}
