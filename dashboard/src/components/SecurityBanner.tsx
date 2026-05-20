export function SecurityBanner() {
  // In Plan 5 this reads the X-LocalLLM-Insecure response header (via a context populated
  // by the first /api/health call). For Plan 1, the dashboard is localhost-only by design.
  return null
}
