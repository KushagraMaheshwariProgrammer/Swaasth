export const ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"];

export const DEFAULT_FILE_ACCEPT =
  ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

export function isSupportedFile(file) {
  if (!file?.name) {
    return false;
  }
  const ext = file.name.split(".").pop()?.toLowerCase();
  return Boolean(ext && ALLOWED_EXTENSIONS.includes(ext));
}

export function isImageFile(file) {
  if (!file) {
    return false;
  }
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (ext && ["jpg", "jpeg", "png"].includes(ext)) {
    return true;
  }
  return file.type?.startsWith("image/") ?? false;
}

export function isPdfFile(file) {
  if (!file) {
    return false;
  }
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") {
    return true;
  }
  return file.type === "application/pdf";
}

export function validateUploadFile(file) {
  if (!file) {
    return { ok: false, error: null };
  }
  if (!isSupportedFile(file)) {
    return {
      ok: false,
      error: "Please upload a valid PDF, JPG, JPEG, or PNG file.",
    };
  }
  return { ok: true, error: null };
}
