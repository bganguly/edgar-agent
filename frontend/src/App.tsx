import ChatInterface from "./components/ChatInterface";

const PORTFOLIO_URL = 'https://bganguly.github.io/#edgar_10k_agent';

function handleBack(e: React.MouseEvent<HTMLAnchorElement>) {
  e.preventDefault();
  try {
    if (window.opener && !window.opener.closed) {
      window.opener.location.href = PORTFOLIO_URL;
      window.close();
      return;
    }
  } catch (_) {}
  window.location.href = PORTFOLIO_URL;
}

export default function App() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <header style={{
        padding: "10px 20px",
        borderBottom: "1px solid #2d3748",
        background: "#1a202c",
      }}>
        <a
          href={PORTFOLIO_URL}
          onClick={handleBack}
          style={{ fontSize: 11, color: "#718096", textDecoration: "none", display: "block", marginBottom: 6, transition: "color 0.15s" }}
          onMouseEnter={e => (e.currentTarget.style.color = "#a5b4fc")}
          onMouseLeave={e => (e.currentTarget.style.color = "#718096")}
        >← Portfolio</a>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "20px" }}>📊</span>
          <span style={{ fontWeight: 600, fontSize: "16px" }}>EDGAR Agent</span>
          <span style={{ color: "#718096", fontSize: "13px" }}>
            — Ask anything about public companies using SEC 10-K filings
          </span>
        </div>
      </header>
      <ChatInterface />
    </div>
  );
}
