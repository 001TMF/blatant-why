/**
 * Convert raw error messages into user-friendly descriptions.
 * Returns empty string for clean cancellations (no message needed).
 */
export function friendlyError(raw: string): string {
  if (!raw || raw.trim().length === 0) return "";

  // Connection errors
  if (raw.includes("ECONNREFUSED") || raw.includes("connection refused"))
    return "MCP server not available. Run /status to check servers.";
  if (raw.includes("ECONNRESET") || raw.includes("socket hang up"))
    return "Connection was reset. The server may have restarted.";

  // Auth / API key errors
  if (raw.includes("TAMARIND_API_KEY") || raw.includes("API key"))
    return "Tamarind API key not set. Add it to .env (free at tamarind.bio)";
  if (raw.includes("ANTHROPIC_API_KEY"))
    return "Anthropic API key not set. Add ANTHROPIC_API_KEY to .env";
  if (raw.includes("401") || raw.includes("Unauthorized"))
    return "Authentication failed. Check your API key.";
  if (raw.includes("403") || raw.includes("Forbidden"))
    return "Access denied. Check your permissions and API key.";

  // File / path errors
  if (raw.includes("ENOENT") || raw.includes("not found"))
    return "File or path not found. Check your campaign directory.";
  if (raw.includes("EACCES") || raw.includes("permission denied"))
    return "Permission denied. Check file permissions.";
  if (raw.includes("ENOSPC"))
    return "Disk full. Free up space and try again.";

  // Rate limiting
  if (raw.includes("rate limit") || raw.includes("429"))
    return "Rate limited. Wait a moment and try again.";

  // Timeout
  if (raw.includes("timeout") || raw.includes("ETIMEDOUT"))
    return "Request timed out. The service may be busy -- try again.";

  // GPU / compute errors
  if (raw.includes("CUDA out of memory"))
    return "GPU out of memory. Try reducing batch size or number of designs.";
  if (raw.includes("RuntimeError") && raw.includes("CUDA"))
    return "GPU error. Check CUDA setup and available memory.";

  // Cancellation (clean, no message)
  if (raw.includes("abort") || raw.includes("AbortError")) return "";
  if (raw.includes("cancel") || raw.includes("SIGINT")) return "";

  // JSON parse errors
  if (raw.includes("SyntaxError") && raw.includes("JSON"))
    return "Received malformed data. The server response was invalid.";

  // Truncate long messages
  return raw.length > 200 ? raw.substring(0, 200) + "..." : raw;
}

/**
 * Determine if an error is transient and worth retrying.
 */
export function isRetryable(raw: string): boolean {
  if (raw.includes("429") || raw.includes("rate limit")) return true;
  if (raw.includes("timeout") || raw.includes("ETIMEDOUT")) return true;
  if (raw.includes("ECONNRESET") || raw.includes("socket hang up"))
    return true;
  if (raw.includes("503") || raw.includes("Service Unavailable")) return true;
  return false;
}

/**
 * Extract a short error code from a raw error for logging.
 */
export function errorCode(raw: string): string {
  const codes = [
    "ECONNREFUSED",
    "ECONNRESET",
    "ENOENT",
    "EACCES",
    "ENOSPC",
    "ETIMEDOUT",
    "AbortError",
  ];
  for (const code of codes) {
    if (raw.includes(code)) return code;
  }
  const httpMatch = raw.match(/\b(4\d{2}|5\d{2})\b/);
  if (httpMatch) return `HTTP_${httpMatch[1]}`;
  return "UNKNOWN";
}
