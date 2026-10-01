import { BarChart3, Bot, ChevronDown, Database, Factory, Globe, Megaphone, MessageSquarePlus, Package, Paperclip, SendHorizontal, X } from 'lucide-react'
import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { aiApi } from '../../api/aiApi'
import Button from '../../components/common/Button'
import ErrorMessage from '../../components/common/ErrorMessage'
import { Toggle } from '../../components/common/Input'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import ChatMessage from './components/ChatMessage'
import { AiInsights, ConversationList } from './components/SidePanels'

const MAX_FILE_MB = 10
const FILE_TYPES = /\.(csv|pdf|xls|xlsx)$/i

// Question shortcuts only; the answers come from the AI engine
const TOPICS = [
  { module: 'sales', icon: BarChart3, tone: 'green', title: 'Sales Analysis', text: 'Trends, top products, regions', q: 'Summarise our sales performance for this month.' },
  { module: 'inventory', icon: Package, tone: 'orange', title: 'Inventory Check', text: 'Stock levels and reorder needs', q: 'Which products are low on stock and need reordering?' },
  { module: 'production', icon: Factory, tone: 'blue', title: 'Production Planning', text: 'What to produce next', q: 'What should we prioritise in production next week?' },
  { module: 'marketing', icon: Megaphone, tone: 'purple', title: 'Marketing Ideas', text: 'Campaigns and content', q: 'Suggest a marketing campaign idea for this season.' },
]

let nextId = 1
const msg = (role, text, extra = {}) => ({ id: nextId++, role, text, at: new Date(), ...extra })

export default function AIAssistantPage() {
  const { user, can } = useAuth()
  const [params, setParams] = useSearchParams()
  const status = useApi(() => aiApi.getStatus(), [])
  const [homeKey, setHomeKey] = useState(0)
  const home = useApi(() => aiApi.getHome(), [homeKey])

  const [messages, setMessages] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [loadingConvo, setLoadingConvo] = useState(false)
  const [attachment, setAttachment] = useState(null)
  const [fileError, setFileError] = useState('')
  const [useCompanyData, setUseCompanyData] = useState(true)
  const [searchWeb, setSearchWeb] = useState(false)
  const [model, setModel] = useState('')
  const listRef = useRef(null)
  const fileRef = useRef(null)
  const inputRef = useRef(null)

  const info = status.data ?? {}
  const available = !status.loading && !status.error && info.available === true
  const models = Array.isArray(info.models) ? info.models : []
  const canAttach = info.features?.attachments === true
  const canSearchWeb = info.features?.web_search === true
  const topics = TOPICS.filter((t) => can(t.module))
  const suggestions = Array.isArray(home.data?.suggestions) ? home.data.suggestions.filter((s) => typeof s === 'string' && s.trim()) : []
  const firstName = (user?.name || user?.username || '').split(' ')[0]

  // Keep the newest message in view
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, pending])

  const send = async (text) => {
    const question = String(text ?? '').trim()
    if (!question || pending || !available) return
    const file = attachment
    setMessages((m) => [...m, msg('user', question, { file: file?.name })])
    setInput('')
    setAttachment(null)
    setPending(true)
    try {
      const res = await aiApi.ask({
        message: question,
        conversation_id: conversationId ?? undefined,
        use_company_data: useCompanyData,
        search_web: canSearchWeb ? searchWeb : undefined,
        model: model || undefined,
        file: canAttach ? file : undefined,
      })
      if (res?.conversation_id) setConversationId(res.conversation_id)
      const reply = typeof res?.reply === 'string' && res.reply.trim() ? res.reply : null
      setMessages((m) => [
        ...m,
        reply
          ? msg('assistant', reply, { sources: res.sources })
          : msg('assistant', 'The assistant returned an empty answer. Please try rephrasing your question.', { error: true }),
      ])
      if (!conversationId) setHomeKey((k) => k + 1) // a new conversation shows up in the list
    } catch (err) {
      setMessages((m) => [...m, msg('assistant', `Sorry, I couldn't get an answer: ${err.message}`, { error: true })])
    } finally {
      setPending(false)
      inputRef.current?.focus()
    }
  }

  // Questions typed in the top search bar arrive as ?q=
  const q = params.get('q')
  const handleQuery = useEffectEvent((question) => {
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        next.delete('q')
        return next
      },
      { replace: true },
    )
    if (available) send(question)
    else setInput(question) // keep it so it isn't lost while the assistant is unavailable
  })
  useEffect(() => {
    if (q && !status.loading) handleQuery(q)
  }, [q, status.loading])

  const openConversation = async (id) => {
    setLoadingConvo(true)
    try {
      const convo = await aiApi.getConversation(id)
      const list = Array.isArray(convo?.messages) ? convo.messages : []
      setMessages(list.map((m) => msg(m.role === 'user' ? 'user' : 'assistant', m.text ?? '', { at: m.created_at ? new Date(m.created_at) : undefined })))
      setConversationId(id)
    } catch (err) {
      setMessages([msg('assistant', `Couldn't open that conversation: ${err.message}`, { error: true })])
    } finally {
      setLoadingConvo(false)
    }
  }

  const newChat = () => {
    setMessages([])
    setConversationId(null)
    setInput('')
    setAttachment(null)
    inputRef.current?.focus()
  }

  const pickFile = (e) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    if (!FILE_TYPES.test(f.name)) return setFileError('Attach a CSV, PDF or Excel file.')
    if (f.size > MAX_FILE_MB * 1024 * 1024) return setFileError(`The file is larger than ${MAX_FILE_MB} MB.`)
    setFileError('')
    setAttachment(f)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const busy = pending || loadingConvo

  return (
    <div className="page">
      <title>AI Assistant | HIPA MASALA</title>
      <div className="ai-hero">
        <div className="page-header__title">
          <div className="page-header__icon">
            <Bot size={30} strokeWidth={2.2} />
          </div>
          <div>
            <h1>AI Assistant</h1>
            <p className="page-header__sub">Your Smart Partner for a Smarter HIPA MASALA</p>
          </div>
        </div>
        <div className="ai-hero__motto" aria-hidden>
          <strong>Ask | Analyze | Plan | Grow</strong>
        </div>
        {available && models.length > 0 && (
          <label className="pill-select">
            <Bot size={18} aria-hidden />
            <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="AI model">
              <option value="">Default model</option>
              {models.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            <ChevronDown size={16} aria-hidden />
          </label>
        )}
      </div>

      {status.error && !status.loading && <ErrorMessage message={status.error.message} onRetry={status.reload} />}
      {!status.loading && !status.error && !available && (
        <div className="ai-notice" role="status">
          <Bot size={22} aria-hidden />
          <div>
            <strong>The AI Assistant isn't connected yet</strong>
            <span>{info.message || 'Questions can be asked once the AI engine is set up on the server. Everything else in the portal works as normal.'}</span>
          </div>
        </div>
      )}

      {topics.length > 0 && (
        <div className="topic-grid">
          {topics.map(({ icon: Icon, title, text, tone, q: question }) => (
            <button key={title} type="button" className={`topic tone-${tone}`} onClick={() => send(question)} disabled={!available || busy}>
              <span className="topic__icon" aria-hidden>
                <Icon size={22} />
              </span>
              <span>
                <strong>{title}</strong>
                <small>{text}</small>
              </span>
            </button>
          ))}
        </div>
      )}

      <div className="grid-main-side">
        <section className="card chat" aria-label="Chat with the AI Assistant">
          <div className="chat__head">
            <strong>{conversationId ? 'Conversation' : 'New conversation'}</strong>
            <Button variant="ghost" size="sm" icon={MessageSquarePlus} onClick={newChat} disabled={busy || messages.length === 0}>
              New Chat
            </Button>
          </div>

          <div className="chat__list" ref={listRef} aria-live="polite" aria-busy={busy || undefined}>
            {messages.length === 0 && !loadingConvo && (
              <div className="chat__welcome">
                <Bot size={34} aria-hidden />
                <p>
                  <strong>Hello{firstName ? ` ${firstName}` : ''}!</strong> Ask a question about sales, stock, production, marketing or finance.
                </p>
                {available && suggestions.length > 0 && (
                  <div className="chat__suggestions">
                    {suggestions.slice(0, 6).map((s, i) => (
                      <button key={`${i}-${s}`} type="button" className="suggestion" onClick={() => send(s)} disabled={busy}>
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {loadingConvo && <div className="skeleton skeleton--list" aria-label="Loading conversation" />}
            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}
            {pending && (
              <div className="chat__msg chat__msg--assistant">
                <span className="chat__avatar" aria-hidden>
                  <Bot size={20} />
                </span>
                <div className="chat__bubble chat__typing" role="status" aria-label="Assistant is answering">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          <form
            className="chat__composer"
            onSubmit={(e) => {
              e.preventDefault()
              send(input)
            }}
          >
            <div className="chat__input-row">
              <textarea
                ref={inputRef}
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={available ? 'Type your question… (Enter to send, Shift+Enter for a new line)' : 'The assistant is not available yet'}
                aria-label="Your question"
                maxLength={2000}
                disabled={!available}
              />
              <button type="submit" className="chat__send" disabled={!available || !input.trim() || busy} aria-label="Send question">
                <SendHorizontal size={20} />
              </button>
            </div>
            <div className="chat__tools">
              <span className="chat__tool">
                <Database size={16} aria-hidden />
                <Toggle label="Use company data" checked={useCompanyData} onChange={setUseCompanyData} disabled={!available} />
              </span>
              {canSearchWeb && (
                <span className="chat__tool">
                  <Globe size={16} aria-hidden />
                  <Toggle label="Search the web" checked={searchWeb} onChange={setSearchWeb} disabled={!available} />
                </span>
              )}
              <span className="chat__spacer" />
              {canAttach &&
                (attachment ? (
                  <span className="chat__attachment">
                    <Paperclip size={14} aria-hidden /> {attachment.name}
                    <button type="button" className="icon-btn icon-btn--sm" onClick={() => setAttachment(null)} aria-label="Remove attached file">
                      <X size={14} />
                    </button>
                  </span>
                ) : (
                  <Button type="button" variant="outline" size="sm" icon={Paperclip} onClick={() => fileRef.current?.click()} disabled={!available}>
                    Attach CSV / PDF / Excel
                  </Button>
                ))}
              <input ref={fileRef} type="file" hidden accept=".csv,.pdf,.xls,.xlsx" onChange={pickFile} />
            </div>
            {fileError && (
              <p className="field__error" role="alert">
                {fileError}
              </p>
            )}
          </form>
        </section>

        {/* When the server can't be reached the banner above already says so */}
        {!status.error && (
          <div className="stack">
            <AiInsights home={home} />
            <ConversationList home={home} activeId={conversationId} onOpen={openConversation} disabled={busy} />
          </div>
        )}
      </div>
    </div>
  )
}
