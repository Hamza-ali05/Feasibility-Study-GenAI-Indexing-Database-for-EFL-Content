/** Patterns that should never appear raw in UI (activity feed, analytics). */
const SUSPICIOUS_QUERY_RE =
  /<|>|\{|\}|`|\\|javascript:|alert\s*\(|onerror\s*=|onload\s*=|union\s+select|sqlite_master|drop\s+table|fromcharcode|constructor\.|%3c|%3e|--|\/\*|\*\/|'\s*or\s+'|or\s+1\s*=\s*1/i;

/**
 * Turn a raw search query into short, human-readable text.
 * Security-test / injection payloads become a plain label; normal
 * EFL queries keep letters and light punctuation only.
 */
export function humanizeSearchQuery(raw) {
  const q = String(raw ?? "").trim();
  if (!q) return "empty query";
  if (SUSPICIOUS_QUERY_RE.test(q)) {
    return "filtered security test query";
  }

  let cleaned = q
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .replace(/[<>"'`\\{}[\]]/g, "")
    .replace(/[^\w\s.,?!:;\-/'()&+%]/gi, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!cleaned) return "filtered search query";
  if (cleaned.length > 56) {
    cleaned = `${cleaned.slice(0, 53)}…`;
  }
  return cleaned;
}

export default humanizeSearchQuery;
