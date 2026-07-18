import ChatInterface from "./components/ChatInterface";

export default function App() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <header style={{
        padding: "12px 20px",
        borderBottom: "1px solid #2d3748",
        background: "#1a202c",
        display: "flex",
        alignItems: "center",
        gap: "10px",
      }}>
        <span style={{ fontSize: "20px" }}>📊</span>
        <span style={{ fontWeight: 600, fontSize: "16px" }}>EDGAR Agent</span>
        <span style={{ color: "#718096", fontSize: "13px" }}>
          — Ask anything about public companies using SEC 10-K filings
        </span>
      </header>
      <ChatInterface />
    </div>
  );
}
