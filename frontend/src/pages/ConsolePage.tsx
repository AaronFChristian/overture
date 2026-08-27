import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  type ExtractResponse,
  type PipelineStage,
  extractSessionStreaming,
  fetchPipelineStages,
} from "../api";
import { PipelineTimeline } from "../components/PipelineTimeline";

type RunState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "error"; message: string }
  | { status: "done"; result: ExtractResponse };

export function ConsolePage() {
  const [transcript, setTranscript] = useState("");
  const [consoleSecret, setConsoleSecret] = useState("");
  const [runState, setRunState] = useState<RunState>({ status: "idle" });
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [reached, setReached] = useState<string[]>([]);
  const [activeDetail, setActiveDetail] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPipelineStages()
      .then((s) => {
        if (!cancelled) setStages(s);
      })
      .catch(() => {
        // Non-fatal: the timeline just won't pre-render its stages.
        // Extraction itself still works, so this shouldn't block the UI.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!transcript.trim() || runState.status === "running") return;

    setRunState({ status: "running" });
    setReached([]);
    setActiveDetail(null);

    try {
      const result = await extractSessionStreaming(
        transcript,
        consoleSecret || undefined,
        (stage, detail) => {
          setReached((prev) => (prev.includes(stage) ? prev : [...prev, stage]));
          setActiveDetail(detail);
        },
      );
      setRunState({ status: "done", result });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      setRunState({ status: "error", message });
    }
  }

  const running = runState.status === "running";
  const showTimeline = running || runState.status === "done";

  return (
    <div className="app-shell">
      <nav className="topbar">
        <Link to="/" className="brand">
          Overture
        </Link>
        <span className="topbar-tag">SE Console</span>
      </nav>

      <main className="page">
        <header className="page-header">
          <h1>Generate a demo</h1>
          <p className="hint">
            Paste a discovery-call transcript. Overture extracts requirements, grounds every one in
            a verbatim quote, and builds a working demo.
          </p>
        </header>

        <form onSubmit={handleSubmit} className="console-form">
          <label className="field-label" htmlFor="transcript">
            Transcript
          </label>
          <textarea
            id="transcript"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="Paste the discovery-call transcript here..."
            rows={14}
            disabled={running}
          />
          <div className="form-row">
            <input
              type="password"
              value={consoleSecret}
              onChange={(e) => setConsoleSecret(e.target.value)}
              placeholder="Console secret (optional)"
              disabled={running}
              className="console-secret-input"
            />
            <button type="submit" disabled={running || !transcript.trim()}>
              {running ? "Extracting..." : "Extract"}
            </button>
          </div>
        </form>

        {showTimeline && stages.length > 0 && (
          <section className="panel">
            <h2 className="panel-title">Pipeline</h2>
            <PipelineTimeline
              stages={stages}
              reached={reached}
              running={running}
              activeDetail={activeDetail}
            />
          </section>
        )}

        {runState.status === "error" && <p className="error">{runState.message}</p>}

        {runState.status === "done" && <ExtractionResult result={runState.result} />}
      </main>
    </div>
  );
}

function ExtractionResult({ result }: { result: ExtractResponse }) {
  const totalRequirements = Object.values(result.requirement_counts).reduce((a, b) => a + b, 0);

  return (
    <section className="panel">
      <div className="result-header">
        <div>
          <span className="eyebrow">Selected blueprint</span>
          <h2 className="panel-title">{result.blueprint_name}</h2>
        </div>
        <span className={`status-pill status-pill--${result.config_status}`}>
          {result.config_status}
        </span>
      </div>

      <p className="result-summary">{result.summary}</p>

      <div className="stat-row">
        <Stat label="Items extracted" value={totalRequirements} />
        <Stat label="In scope" value={result.scope_counts.in_scope ?? 0} />
        <Stat label="Out of scope" value={result.scope_counts.out_of_scope ?? 0} />
        <Stat label="Needs clarification" value={result.scope_counts.needs_clarification ?? 0} />
        <Stat label="Chunks indexed" value={result.chunks_indexed} />
      </div>

      <p className="session-id">
        Session <code>{result.session_id}</code>
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
        <Link to={`/demo/${result.demo_token}`} className="cta-link">
          Open the generated demo &rarr;
        </Link>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
