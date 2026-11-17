/**
 * Untrusted text sanitization for the frontend.
 * Strictly adheres to Invariant 10:
 * Strips ANSI escapes, Unicode bidirectional overrides (RLO/LRO), and control characters.
 */

const ANSI_REGEX = /\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g;
const BIDI_REGEX = /[\u202A-\u202E\u2066-\u2069]/g;
const CONTROL_CHARS_REGEX = /[\x00-\x08\x0B-\x1F\x7F]/g;

export function sanitize(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(ANSI_REGEX, "")
    .replace(BIDI_REGEX, "")
    .replace(CONTROL_CHARS_REGEX, "");
}
