/**
 * Backend base URL, injected at build time. Falls back to a same-origin
 * relative path in production (the app is served by the same Container
 * App as the API -- see decisions.md D-0040), and to the local FastAPI
 * dev server's default port for local development.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface DemoConfig {
  blueprint_id: string;
  blueprint_name: string;
  sample_questions: string[];
}

export interface AskResponse {
  answer: string;
  citations: string[];
}

export interface ExtractResponse {
  session_id: string;
  summary: string;
  requirement_counts: Record<string, number>;
  scope_counts: Record<string, number>;
  blueprint_id: string;
  blueprint_name: string;
  config_status: string;
  validation_errors: string[];
  sample_questions: string[];
  demo_token: string | null;
  chunks_indexed: number;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Response body wasn't JSON -- fall back to statusText, already set above.
    }
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export async function fetchDemoConfig(token: string): Promise<DemoConfig> {
  const response = await fetch(`${API_BASE_URL}/api/v1/demo/${encodeURIComponent(token)}`);
  return handleResponse<DemoConfig>(response);
}

export async function askQuestion(token: string, question: string): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/demo/${encodeURIComponent(token)}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return handleResponse<AskResponse>(response);
}

export interface PipelineStage {
  id: string;
  label: string;
}

export async function fetchPipelineStages(): Promise<PipelineStage[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/sessions/stages`);
  return handleResponse<PipelineStage[]>(response);
}

/**
 * Streams extraction progress via Server-Sent Events.
 *
 * Deliberately uses fetch + a manual stream reader rather than the
 * browser's EventSource API: EventSource only issues GET requests and
 * can't send a request body or custom headers, and this endpoint needs
 * both (the transcript, and the optional console secret). See
 * decisions.md D-0050.
 */
export async function extractSessionStreaming(
  transcript: string,
  consoleSecret: string | undefined,
  onProgress: (stage: string, detail: string) => void,
): Promise<ExtractResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (consoleSecret) headers["X-Console-Secret"] = consoleSecret;

  const response = await fetch(`${API_BASE_URL}/api/v1/sessions/extract/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({ transcript }),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Not JSON -- statusText already set above.
    }
    throw new ApiError(detail, response.status);
  }
  if (!response.body) throw new ApiError("No response stream available.", 500);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ExtractResponse | null = null;
  let streamError: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line. Anything after the
    // last separator is an incomplete frame -- keep it buffered.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      if (!frame.trim()) continue;
      let eventName = "message";
      let dataLine = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) eventName = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataLine = line.slice(6);
      }
      if (!dataLine) continue;

      if (eventName === "progress") {
        const parsed = JSON.parse(dataLine) as { stage: string; detail: string };
        onProgress(parsed.stage, parsed.detail);
      } else if (eventName === "result") {
        result = JSON.parse(dataLine) as ExtractResponse;
      } else if (eventName === "error") {
        streamError = (JSON.parse(dataLine) as { detail: string }).detail;
      }
    }
  }

  if (streamError) throw new ApiError(streamError, 500);
  if (!result) throw new ApiError("Stream ended without returning a result.", 500);
  return result;
}

export async function extractSession(
  transcript: string,
  consoleSecret?: string,
): Promise<ExtractResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (consoleSecret) headers["X-Console-Secret"] = consoleSecret;

  const response = await fetch(`${API_BASE_URL}/api/v1/sessions/extract`, {
    method: "POST",
    headers,
    body: JSON.stringify({ transcript }),
  });
  return handleResponse<ExtractResponse>(response);
}
