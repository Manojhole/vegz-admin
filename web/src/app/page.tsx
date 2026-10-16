const API_ORIGIN = (process.env.NEXT_PUBLIC_VEGZ_ADMIN_API_URL || "http://localhost:8000").replace(/\/$/, "");

export default function AdminHomePage() {
  return (
    <main className="portal-shell">
      <header className="portal-header">
        <a className="brand" href="/" aria-label="Vegz admin home"><span className="brand-mark">V</span><span>vegz<span className="period">.</span></span></a>
        <span className="portal-label">OPERATIONS</span>
        <a className="open-link" href={API_ORIGIN} target="_blank" rel="noreferrer">Open console separately ↗</a>
      </header>
      <section className="portal-intro">
        <p className="eyebrow">PLATFORM CONTROL CENTER</p>
        <h1>One console.<br /><span>Full operational visibility.</span></h1>
        <p>Partner onboarding, product moderation, customer records, orders and audit activity are served by FastAPI. This Next.js entry point keeps those existing workflows available while the screens migrate.</p>
      </section>
      <section className="live-portal">
        <div className="portal-bar"><span className="live-dot" /> <strong>Live admin console</strong><span className="portal-origin">{API_ORIGIN}</span></div>
        <iframe title="Vegz Admin console" src={API_ORIGIN} loading="eager" />
      </section>
      <footer>Vegz Admin · Internal operations console.</footer>
    </main>
  );
}
