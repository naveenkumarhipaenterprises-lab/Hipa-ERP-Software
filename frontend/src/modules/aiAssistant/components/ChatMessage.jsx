import { Bot, ExternalLink, Paperclip } from 'lucide-react'
import { formatTime } from '../../../utils/formatters'

/** One chat bubble. Text is shown as plain text (line breaks kept); nothing is rendered as HTML. */
export default function ChatMessage({ message: m }) {
  const sources = Array.isArray(m.sources) ? m.sources : []
  return (
    <div className={`chat__msg chat__msg--${m.role} ${m.error ? 'chat__msg--error' : ''}`}>
      {m.role === 'assistant' && (
        <span className="chat__avatar" aria-hidden>
          <Bot size={20} />
        </span>
      )}
      <div className="chat__bubble">
        <span className="sr-only">{m.role === 'user' ? 'You said: ' : 'Assistant: '}</span>
        <p className="chat__text">{m.text}</p>
        {m.file && (
          <span className="chat__file">
            <Paperclip size={13} aria-hidden /> {m.file}
          </span>
        )}
        {sources.length > 0 && (
          <ul className="chat__sources" aria-label="Sources">
            {sources.map((s, i) => (
              <li key={i}>
                {typeof s.url === 'string' && /^https?:\/\//.test(s.url) ? (
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="link">
                    {s.title || s.url} <ExternalLink size={11} aria-hidden />
                  </a>
                ) : (
                  s.title
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      {m.at && (
        <time className="chat__time" dateTime={new Date(m.at).toISOString()}>
          {formatTime(m.at)}
        </time>
      )}
    </div>
  )
}
