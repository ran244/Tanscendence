import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { get, post } from '../api/client'

const issueTypes = ['Payment problem', 'Item not as described', 'Seller unresponsive', 'Bug on the site', 'Other']

export default function ReportIssue() {
  const [searchParams] = useSearchParams()
  const selectedTicketId = Number(searchParams.get('ticket')) || null
  const [submitted, setSubmitted] = useState(false)
  const [type, setType] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [tickets, setTickets] = useState([])
  const [replies, setReplies] = useState({})
  const [busy, setBusy] = useState(null)

  const load = () => get('/notifications/support/tickets/?page_size=100')
    .then((data) => setTickets(data.results || []))
    .catch((err) => setError(err.message))

  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!selectedTicketId || tickets.length === 0) return
    document.getElementById(`ticket-${selectedTicketId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [selectedTicketId, tickets])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    try {
      await post('/notifications/support/tickets/', { subject: type, message: description })
      setSubmitted(true)
      setType('')
      setDescription('')
      await load()
    } catch (err) { setError(err.message) }
  }

  const reply = async (event, ticket) => {
    event.preventDefault()
    const message = replies[ticket.id]?.trim()
    if (!message) return
    setBusy(ticket.id); setError('')
    try {
      await post(`/notifications/support/tickets/${ticket.id}/`, { message })
      setReplies((old) => ({ ...old, [ticket.id]: '' }))
      await load()
    } catch (err) { setError(err.message) }
    finally { setBusy(null) }
  }

  return (
    <Layout>
      <section style={{ padding: '30px 0 90px' }}>
        <h2 style={{ marginBottom: 26 }}>Report an issue</h2>

        {error && <p className="form-error" role="alert">{error}</p>}

        {submitted ? (
          <div className="panel support-submitted" role="status">
            <p>Thanks &mdash; your report was submitted. Replies will appear in your notifications and in the ticket below.</p>
            <button className="btn btn-outline btn-sm" type="button" onClick={() => setSubmitted(false)}>Report another issue</button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="form-narrow" style={{ maxWidth: 480, textAlign: 'left' }}>
            <div className="field">
              <label>Choose issue type</label>
              <select className="input" required value={type} onChange={(event) => setType(event.target.value)}>
                <option value="" disabled>choose issue type</option>
                {issueTypes.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Write issue description</label>
              <textarea className="textarea" placeholder="write issue description" value={description} onChange={(event) => setDescription(event.target.value)} required />
            </div>
            <button className="btn btn-outline" type="submit">submit report</button>
          </form>
        )}

        <h3 style={{ marginTop: 40 }}>Your support tickets</h3>
        {tickets.length === 0 ? <p className="sub">No previous tickets.</p> : tickets.map((ticket) => (
          <article
            className={`support-ticket ${selectedTicketId === ticket.id ? 'selected' : ''}`}
            id={`ticket-${ticket.id}`}
            key={ticket.id}
          >
            <div className="support-ticket-head">
              <div><strong>#{ticket.id} {ticket.subject}</strong><div className="sub">Updated {new Date(ticket.updated_at).toLocaleString()}</div></div>
              <span className="tag tag-upcoming">{ticket.status_display}</span>
            </div>
            <div className="support-thread">
              {(ticket.messages || []).map((message) => {
                const fromUser = message.author_username === ticket.reporter_username
                return <div className={`support-message ${fromUser ? 'from-user' : 'from-admin'}`} key={message.id}><div><strong>{fromUser ? 'You' : 'Support team'}</strong><time>{new Date(message.created_at).toLocaleString()}</time></div><p>{message.message}</p></div>
              })}
            </div>
            {!['RESOLVED', 'CLOSED'].includes(ticket.status) && (
              <form className="support-reply" onSubmit={(event) => reply(event, ticket)}>
                <input className="input" aria-label={`Reply to ticket ${ticket.id}`} placeholder="Add more information" value={replies[ticket.id] || ''} onChange={(event) => setReplies((old) => ({ ...old, [ticket.id]: event.target.value }))} required />
                <button className="btn btn-outline btn-sm" disabled={busy === ticket.id}>Reply</button>
              </form>
            )}
          </article>
        ))}
      </section>
    </Layout>
  )
}
