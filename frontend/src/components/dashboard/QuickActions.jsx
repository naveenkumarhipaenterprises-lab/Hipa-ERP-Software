/** Grid of coloured shortcut tiles. actions: [{ label, icon, tone, onClick }] */
export default function QuickActions({ actions, columns = 2, layout = 'row' }) {
  return (
    <div className={`quick-actions quick-actions--${layout}`} style={{ '--qa-cols': columns }}>
      {actions.map(({ label, icon: Icon, tone = 'green', onClick }) => (
        <button key={label} className={`quick-action tone-${tone}`} onClick={onClick}>
          {Icon && <Icon size={layout === 'stack' ? 24 : 18} />}
          <span>{label}</span>
        </button>
      ))}
    </div>
  )
}
