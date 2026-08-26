import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, type ExtractResponse, extractSession } from "../api";

type RunState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "error"; message: string }
  | { status: "done"; result: ExtractResponse };

export function ConsolePage() {
  const [transcript, setTranscript] = useState("");
  const [consoleSecret, setConsoleSecret] = useState("");
  const [runState, setRunState] = useState<RunState>({ status: "idle" });

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!transcript.trim() || runState.status === "running") return;

    setRunState({ status: "running" });
    try {
      const result = await extractSession(transcript, consoleSecret || undefined);
      setRunState({ status: "done", result });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      setRunState({ status: "error", message });
    }
  }

  const running = runState.status === "running";

  return (
    <main className="page">
      <header className="demo-header">
        <h1>Overture console</h1>
        <p className="hint">
          Paste a discovery-call transcript to extract requirements and generate a demo.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="console-form">
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="Paste the transcript here..."
          rows={12}
          disabled={running}
        />
        <input
          type="password"
          value={consoleSecret}
          onChange={(e) => setConsoleSecret(e.target.value)}
          placeholder="Console secret (leave blank if not required)"
          disabled={running}
          className="console-secret-input"
        />
        <button type="submit" disabled={running || !transcript.trim()}>
          {running ? "Extracting... this can take a minute" : "Extract"}
        </button>
      </form>

      {runState.status === "error" && <p className="error">{runState.message}</p>}

      {runState.status === "done" && <ExtractionResult result={runState.result} />}
    </main>
  );
}

function ExtractionResult({ result }: { result: ExtractResponse }) {
  const totalRequirements = Object.values(result.requirement_counts).reduce((a, b) => a + b, 0);

  return (
    <section className="extraction-result">
      <h2>{result.blueprint_name}</h2>
      <p>{result.summary}</p>

      <dl className="stat-grid">
        <dt>Requirements extracted</dt>
        <dd>{totalRequirements}</dd>
        <dt>In scope</dt>
        <dd>{result.scope_counts.in_scope ?? 0}</dd>
        <dt>Out of scope</dt>
        <dd>{result.scope_counts.out_of_scope ?? 0}</dd>
        <dt>Needs clarification</dt>
        <dd>{result.scope_counts.needs_clarification ?? 0}</dd>
        <dt>Chunks indexed</dt>
        <dd>{result.chunks_indexed}</dd>
      </dl>

      <p>
        Config status: <strong>{result.config_status}</strong>
      </p>

      {result.validation_errors.length > 0 && (
        <div className="error">
          <p>Validation failed:</p>
          <ul>
            {result.validation_errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {result.demo_token && (
        <p>
          <Link to={`/demo/${result.demo_token}`} className="demo-link">
            Open the demo &rarr;
          </Link>
        </p>
      )}
    </section>
  );
}
