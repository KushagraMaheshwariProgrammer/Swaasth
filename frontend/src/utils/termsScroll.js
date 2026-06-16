export const TERMS_SCROLL_THRESHOLD_PX = 24;

export function hasScrolledToBottom(element, threshold = TERMS_SCROLL_THRESHOLD_PX) {
  if (!element) {
    return false;
  }
  return (
    element.scrollHeight <= element.clientHeight + threshold ||
    element.scrollTop + element.clientHeight >= element.scrollHeight - threshold
  );
}
