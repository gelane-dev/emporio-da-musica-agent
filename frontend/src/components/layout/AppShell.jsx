export default function AppShell({ sidebarOpen, onCloseSidebar, sidebar, children }) {
  return (
    <div className="shell">
      <div className={`shell__sidebar ${sidebarOpen ? 'is-open' : ''}`}>{sidebar}</div>
      {sidebarOpen ? <button type="button" className="shell__scrim" aria-label="Fechar menu" onClick={onCloseSidebar} /> : null}
      <main className="shell__main">{children}</main>
    </div>
  )
}
