export default function Loader({ fullScreen = false, label = 'Loading…' }) {
  return (
    <div className={fullScreen ? 'loader loader--full' : 'loader'} role="status">
      <span className="loader__leaf" aria-hidden />
      <span className="loader__label">{label}</span>
    </div>
  )
}
