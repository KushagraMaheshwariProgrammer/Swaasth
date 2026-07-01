import { useEffect } from "react";

export default function ReportPdfViewer({
  blobUrl,
  title,
  onClose,
  onDownload,
  onShare,
  busyAction = "",
}) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  return (
    <div className="report-pdf-overlay" role="dialog" aria-modal="true" aria-label={title}>
      <div className="report-pdf-shell">
        <header className="report-pdf-header">
          <button type="button" className="bill-editor-secondary" onClick={onClose}>
            Close
          </button>
          <strong className="report-pdf-title">{title}</strong>
          <div className="report-pdf-header-actions">
            <button
              type="button"
              className="bill-editor-secondary"
              onClick={onDownload}
              disabled={Boolean(busyAction)}
            >
              {busyAction === "download" ? "Preparing…" : "Download"}
            </button>
            <button
              type="button"
              className="analyze-btn report-pdf-share-btn"
              onClick={onShare}
              disabled={Boolean(busyAction)}
            >
              {busyAction === "share" ? "Sharing…" : "Share"}
            </button>
          </div>
        </header>
        <iframe
          src={blobUrl}
          title={title}
          className="report-pdf-frame"
        />
      </div>
    </div>
  );
}
