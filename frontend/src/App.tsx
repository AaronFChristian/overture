import { Link, Route, Routes } from "react-router-dom";
import { ConsolePage } from "./pages/ConsolePage";
import { DemoPage } from "./pages/DemoPage";

function Landing() {
  return (
    <div className="app-shell">
      <nav className="topbar">
        <span className="brand">Overture</span>
      </nav>
      <main className="page">
        <header className="page-header">
          <span className="eyebrow">Demo runtime</span>
          <h1>Discovery transcript in, working demo out.</h1>
          <p className="hint">
            Open a link an SE shared with you to see a specific demo, or head to the console to
            generate one from a transcript.
          </p>
        </header>
        <Link to="/console" className="cta-link">
          Open the SE console &rarr;
        </Link>
      </main>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/console" element={<ConsolePage />} />
      <Route path="/demo/:token" element={<DemoPage />} />
    </Routes>
  );
}
