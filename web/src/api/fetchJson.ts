/** An error whose message a non-expert can act on; `status` is the HTTP status when the server answered. */
export class ApiError extends Error {
  status?: number;
  retryAfter?: number;

  constructor(message: string, status?: number, retryAfter?: number) {
    super(message);
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

/** fetch + JSON, turning every failure into an ApiError. `timeoutMs` gives up on a server that doesn't answer. */
export async function fetchJson<T>(url: string, options: RequestInit & { timeoutMs?: number } = {}): Promise<T> {
  const { timeoutMs, ...init } = options;
  let response: Response;
  try {
    response = await fetch(url, timeoutMs ? { ...init, signal: AbortSignal.timeout(timeoutMs) } : init);
  } catch {
    throw new ApiError(`Can't reach ${new URL(url, location.href).origin}.`);
  }
  // A static host answers a missing file with the site's own page instead of a 404.
  if (response.ok && url.endsWith(".json") && response.headers.get("Content-Type")?.includes("text/html")) {
    throw new ApiError(`${url} doesn't exist.`, 404);
  }
  const text = await response.text();
  const body = parse(text);
  if (!response.ok) {
    const retry = Number(response.headers.get("Retry-After")) || undefined;
    throw new ApiError(errorMessage(body) ?? `The server answered ${response.status} ${response.statusText}.`,
                       response.status, retry);
  }
  if (text && body === undefined) throw new ApiError(`Couldn't read ${url}.`);
  return body as T;
}

function parse(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

/** FastAPI sends {"detail": "..."} for our own errors and {"detail": [{msg}, …]} for invalid input. */
function errorMessage(body: unknown): string | undefined {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item: { msg?: string }) => item.msg?.replace(/^Value error, /, "")).join(" ");
  return undefined;
}
