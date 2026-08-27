import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, askQuestion, type DemoConfig, fetchDemoConfig } from "../api";

interface ConversationTurn {
  question: string;
  answer: string;
  citations: string[];
}

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; config: DemoConfig };

// The demo runtime's stages are fast and fixed (embed -> search ->
// generate), so unlike the extraction pipeline (D-0049) these aren't
// streamed from the backend -- they're advanced on a local timer
// purely to make the retrieval steps legible during a demo. Labeled
// honestly here so the distinction isn't lost: these reflect what the
// backend genuinely does, but the timing is indicative, not measured.
const ASK_STAGES = [
  "Embedding your question (256-dim hashing embedder)",
  "Searching indexed chunks by cosine similarity in pgvector",
  "Generating a grounded answer with citations",
];

export function DemoPage() {
  const { token } = useParams<{ token: string }>();
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askStage, setAskStage] = useState(0);
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [askError, setAskError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchDemoConfig(token)
      .then((config) => {
        if (!cancelled) setLoadState({ status: "ready", config });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof ApiError ? err.message : "Something went wrong.";
        setLoadState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Advance the visible retrieval stage while a request is in flight.
  useEffect(() => {
    if (!asking) return;
    const timer = setInterval(() => {
      setAskStage((s) => Math.min(s + 1, ASK_STAGES.length - 1));
    }, 900);
    return () => clearInterval(timer);
  }, [asking]);

  async function submitQuestion(q: string) {
    if (!token || !q.trim() || asking) return;
    setAsking(true);
    setAskStage(0);
    setAskError(null);
    try {
      const result = await askQuestion(token, q);
      setConversation((prev) => [
        ...prev,
        { question: q, answer: result.answer, citations: result.citations },
      ]);
      setQuestion("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      setAskError(message);
    } finally {
      setAsking(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void submitQuestion(question);
  }

  if (!token) {
    return (
      <Shell>
        <h1>This demo link isn't working</h1>
        <p className="error">No demo token provided in the URL.</p>
      </Shell>
    );
  }

  if (loadState.status === "loading") {
    return (
      <Shell>
        <p className="hint">Loading demo...</p>
      </Shell>
    );
  }

  if (loadState.status === "error") {
    return (
      <Shell>
        <h1>This demo link isn't working</h1>
        <p className="error">{loadState.message}</p>
      </Shell>
    );
  }

  const { config } = loadState;

  return (
    <Shell tag={config.blueprint_name}>
      <header className="page-header">
        <span className="eyebrow">Grounded demo</span>
        <h1>{config.blueprint_name}</h1>
        <p className="hint">
          Answers come only from the indexed transcript. If the source doesn't support an answer,
          this demo says so instead of guessing.
        </p>
      </header>

      {config.sample_questions.length > 0 && conversation.length === 0 && (
        <div className="sample-questions">
          {config.sample_questions.map((sq) => (
            <button
              key={sq}
              type="button"
              className="sample-question"
              onClick={() => void submitQuestion(sq)}
              disabled={asking}
            >
              {sq}
            </button>
          ))}
        </div>
      )}

      <div className="conversation">
        {conversation.map((turn, i) => (
          <article className="turn" key={i}>
            <p className="turn-question">{turn.question}</p>
            <p className="turn-answer">{turn.answer}</p>
            {turn.citations.length > 0 && (
              <details className="citations">
                <summary>Retrieved sources ({turn.citations.length})</summary>
                <ul>
                  {turn.citations.map((c, ci) => (
                    <li key={ci}>
                      <span className="citation-index">[{ci + 1}]</span> {c}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </article>
        ))}

        {asking && (
          <div className="thinking-panel">
            {ASK_STAGES.map((label, i) => (
              <div
                key={label}
                className={`thinking-stage ${
                  i < askStage ? "is-done" : i === askStage ? "is-active" : "is-pending"
                }`}
              >
                <span aria-hidden="true">{i < askStage ? "✓" : i === askStage ? "●" : "○"}</span>
                {label}
              </div>
            ))}
          </div>
        )}
      </div>

      {askError && <p className="error">{askError}</p>}

      <form onSubmit={handleSubmit} className="ask-form">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question..."
          disabled={asking}
        />
        <button type="submit" disabled={asking || !question.trim()}>
          Ask
        </button>
      </form>
    </Shell>
  );
}

function Shell({ children, tag }: { children: React.ReactNode; tag?: string }) {
  return (
    <div className="app-shell">
      <nav className="topbar">
        <Link to="/" className="brand">
          Overture
        </Link>
        {tag && <span className="topbar-tag">{tag}</span>}
      </nav>
      <main className="page">{children}</main>
    </div>
  );
}
