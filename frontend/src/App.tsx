const steps = [
  'sources',
  'index+extract',
  'summarize',
  'proposals',
  'review',
  'apply',
  'analytics',
]

export function App() {
  return (
    <div className="layout">
      <aside className="leftRail">
        <h2>Workflow v2</h2>
        <p className="sub">Memory-first stepper</p>
        <ol>
          {steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </aside>

      <main className="mainPanel">
        <section className="healthStrip">
          <strong>System Health</strong>
          <span>API: unknown</span>
          <span>Queue: unknown</span>
          <span>DB: unknown</span>
        </section>

        <section className="stepCards">
          {steps.map((step) => (
            <article className="card" key={step}>
              <h3>{step}</h3>
              <p>Placeholder content for {step} step.</p>
            </article>
          ))}
        </section>
      </main>

      <aside className="consolePanel">
        <h3>Run Console</h3>
        <p>Live run events will stream/poll here.</p>
        <pre>[placeholder] waiting for workflow job...</pre>
      </aside>
    </div>
  )
}
