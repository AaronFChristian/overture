import { Route, Routes } from "react-router-dom";
import { DemoPage } from "./pages/DemoPage";

function NoTokenLanding() {
  return (
    <main className="page">
      <h1>Overture</h1>
      <p className="hint">
        This is the demo runtime -- open a link an SE shared with you to see a specific demo.
      </p>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<NoTokenLanding />} />
      <Route path="/demo/:token" element={<DemoPage />} />
    </Routes>
  );
}
