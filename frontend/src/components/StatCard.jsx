export default function StatCard({ label, value, color }) {
  return (
    <div
      className={`card stat-card-compact${color ? ' stat-card-accent' : ''}`}
      style={color ? { '--stat-accent': color } : undefined}
    >
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: color || 'var(--text)' }}>{value}</div>
    </div>
  );
}
