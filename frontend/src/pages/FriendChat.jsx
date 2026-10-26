import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { get, post } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function FriendChat() {
  const { id } = useParams(); const { user } = useAuth(); const [friend, setFriend] = useState(null); const [messages, setMessages] = useState([]); const [draft, setDraft] = useState(''); const [error, setError] = useState(''); const endRef = useRef(null)
  const load = useCallback(async () => { try { const [profile, thread] = await Promise.all([get(`/accounts/users/${id}/`), get(`/notifications/chats/${id}/`)]); setFriend(profile); setMessages(thread.results || []) } catch (err) { setError(err.message) } }, [id])
  useEffect(() => { load(); const timer = window.setInterval(load, 4000); return () => window.clearInterval(timer) }, [load])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages.length])
  const send = async (event) => { event.preventDefault(); const message = draft.trim(); if (!message) return; try { const created = await post(`/notifications/chats/${id}/`, { message }); setMessages((old) => [...old, created]); setDraft('') } catch (err) { setError(err.message) } }
  return <Layout><section className="chat-page"><div className="chat-heading"><div><h2>{friend ? `Chat with ${friend.username}` : 'Friend chat'}</h2><Link to={`/friends/${id}`}>View profile</Link></div><Link className="btn btn-outline btn-sm" to="/friends">All friends</Link></div>{error && <p role="alert" className="form-error">{error}</p>}<div className="chat-thread" aria-live="polite">{messages.length === 0 && <p className="sub">No messages yet. Say hello.</p>}{messages.map((item) => <div className={`chat-message ${item.sender === user?.id ? 'mine' : 'theirs'}`} key={item.id}><strong>{item.sender === user?.id ? 'You' : item.sender_username}</strong><p>{item.message}</p><time>{new Date(item.created_at).toLocaleString()}</time></div>)}<div ref={endRef} /></div><form className="chat-compose" onSubmit={send}><label htmlFor="friend-message">Message</label><textarea id="friend-message" className="textarea" maxLength="2000" value={draft} onChange={(event) => setDraft(event.target.value)} required/><button className="btn btn-primary">Send message</button></form></section></Layout>
}
