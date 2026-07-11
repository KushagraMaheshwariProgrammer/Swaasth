/**
 * React Router sets location.key to "default" for the first history entry.
 * Any later push/replace gets a unique key, so we can go back safely.
 */
export function canNavigateBack(location) {
  return Boolean(location?.key && location.key !== "default");
}
