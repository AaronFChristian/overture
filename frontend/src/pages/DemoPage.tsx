import { type FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
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

export function DemoPage() {
  const { token } = useParams<{ token: string }>();
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
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

  async function submitQuestion(q: string) {
    if (!token || !q.trim() || asking) return;
    setAsking(true);
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
      <main className="page">
        <h1>This demo link isn't working</h1>
        <p className="error">No demo token provided in the URL.</p>
      </main>
    );
  }

  if (loadState.status === "loading") {
    return (
      <main className="page">
        <p>Loading demo...</p>
      </main>
    );
  }

  if (loadState.status === "error") {
    return (
      <main className="page">
        <h1>This demo link isn't working</h1>
        <p className="error">{loadState.message}</p>
      </main>
    );
  }

  const { config } = loadState;

  return (
    <main className="page">
      <header className="demo-header">
        <h1>{config.blueprint_name}</h1>
        <p className="hint">Ask a question below, or try one of the examples.</p>
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
          <div className="turn" key={i}>
            <p className="turn-question">{turn.question}</p>
            <p className="turn-answer">{turn.answer}</p>
            {turn.citations.length > 0 && (
              <details className="citations">
                <summary>Sources ({turn.citations.length})</summary>
                <ul>
                  {turn.citations.map((c, ci) => (
                    <li key={ci}>{c}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}
        {asking && <p className="thinking">Thinking...</p>}
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
    </main>
  );
}
