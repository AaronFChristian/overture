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
