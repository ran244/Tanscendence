import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { del, get, post } from '../api/client'

function normalizePresence(results) {
  if (Array.isArray(results)) return Object.fromEntries(results.map((row) => [row.user_id, row]))
  return Object.fromEntries(Object.entries(results || {}).map(([userId, online]) => [userId, { online: Boolean(online) }]))
}

function FriendProfileModal({ profile, online, onClose }) {
  useEffect(() => {
    const closeOnEscape = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])
  return <div className="modal-backdrop" onClick={onClose}><article className="modal friend-profile-modal" role="dialog" aria-modal="true" aria-labelledby="friend-profile-title" onClick={(event) => event.stopPropagation()}><button className="modal-close" type="button" aria-label="Close profile" onClick={onClose}>×</button><div className="modal-body friend-profile-card"><img className="friend-profile-avatar" src={profile.avatar || '/default-avatar.svg'} alt=""/><div><span className={`status-light ${online ? 'online' : ''}`} /> {online ? 'Online' : 'Offline'}<h2 id="friend-profile-title">{profile.username}</h2><p>{profile.bio || 'No biography provided.'}</p><p className="sub">Member since {new Date(profile.date_joined).toLocaleDateString()}</p>{profile.friend_status === 'friends' && <div className="friend-profile-actions"><Link className="btn btn-primary" to={`/friends/${profile.id}/chat`}>Open chat</Link></div>}</div></div></article></div>
}

export default function Friends() {
  const [friends, setFriends] = useState([])
  const [requests, setRequests] = useState([])
  const [presence, setPresence] = useState({})
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [selectedProfile, setSelectedProfile] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    try {
      const [friendPage, requestPage] = await Promise.all([get('/accounts/friends/'), get('/accounts/friends/requests/')])
      const rows = friendPage.results || []
      setFriends(rows); setRequests(requestPage.results || [])
      if (rows.length) {
        const result = await get(`/accounts/presence/?ids=${rows.map((friend) => friend.id).join(',')}`)
        setPresence(normalizePresence(result.results))
      } else setPresence({})
      setError('')
    } catch (err) { setError(err.message) }
  }
  useEffect(() => { load() }, [])

  const search = async (event) => {
    event.preventDefault(); setError(''); setMessage('')
    if (query.trim().length < 2) return setError('Enter at least two characters.')
    try { const data = await get(`/accounts/users/?search=${encodeURIComponent(query.trim())}`); setResults(data.results || []) } catch (err) { setError(err.message) }
  }
  const add = async (person) => {
    setError('')
    try {
      const data = await post('/accounts/friends/request/', { username: person.username })
      setMessage(data.message)
      setResults((old) => old.map((row) => row.id === person.id ? { ...row, friend_status: 'pending_outgoing' } : row))
      await load()
    } catch (err) { setError(err.message) }
  }
  const act = async (path) => { setError(''); try { const data = await post(path); setMessage(data.message); await load() } catch (err) { setError(err.message) } }
  const remove = async (friend) => { if (!window.confirm(`Remove ${friend.username} from your friends?`)) return; try { await del(`/accounts/friends/${friend.id}/`); setSelectedProfile(null); setMessage(`${friend.username} was removed from your friends.`); await load() } catch (err) { setError(err.message) } }

  return <Layout><section className="friends-page"><div className="friends-heading"><div><h2>Friends</h2><p>Search, add, accept and manage your friends in one place.</p></div></div>
    <form className="friend-search-form" onSubmit={search}><input className="input" type="search" aria-label="Search users by username" placeholder="Search by username" value={query} onChange={(event) => setQuery(event.target.value)} /><button className="btn btn-primary">Search</button></form>
    {message && <p className="admin-notice" role="status">{message}</p>}{error && <p className="form-error" role="alert">{error}</p>}
    {results.length > 0 && <div className="friend-search-results"><h3>Search results</h3>{results.map((person) => <div className="list-row" key={person.id}><img src={person.avatar || '/default-avatar.svg'} alt=""/><button className="friend-name-button flex1" type="button" onClick={() => setSelectedProfile(person)}><strong>{person.username}</strong><span className="sub">{person.is_online ? 'Online' : 'Offline'}</span></button>{person.friend_status === 'friends' ? <button className="btn btn-outline btn-sm" type="button" onClick={() => setSelectedProfile(person)}>View profile</button> : <button className="btn btn-primary btn-sm" type="button" disabled={person.friend_status === 'pending_outgoing' || person.friend_status === 'pending_incoming'} onClick={() => add(person)}>{person.friend_status === 'pending_outgoing' ? 'Request sent' : person.friend_status === 'pending_incoming' ? 'Request received' : 'Add friend'}</button>}</div>)}</div>}
    <h3>Incoming requests</h3>{requests.length === 0 ? <p className="sub">No pending requests.</p> : requests.map((request) => <div className="list-row" key={request.id}><img src={request.from.avatar || '/default-avatar.svg'} alt=""/><button className="friend-name-button flex1" type="button" onClick={() => setSelectedProfile(request.from)}><strong>{request.from.username}</strong><span className="sub">View profile</span></button><button className="btn btn-primary btn-sm" onClick={() => act(`/accounts/friends/requests/${request.id}/accept/`)}>Accept</button><button className="btn btn-outline btn-sm" onClick={() => act(`/accounts/friends/requests/${request.id}/decline/`)}>Reject</button></div>)}
    <h3 className="friends-list-heading">Your friends</h3>{friends.length === 0 ? <div className="empty-state"><p>Search for someone to add as a friend.</p></div> : friends.map((friend) => <div className="list-row friend-row" key={friend.id}><img src={friend.avatar || '/default-avatar.svg'} alt=""/><button className="friend-name-button flex1" type="button" onClick={() => setSelectedProfile(friend)}><strong>{friend.username}</strong><span className="sub">{presence[friend.id]?.online ? 'Online' : 'Offline'}</span></button><Link className="btn btn-primary btn-sm" to={`/friends/${friend.id}/chat`}>Chat</Link><button className="btn btn-outline btn-sm" onClick={() => remove(friend)}>Remove</button></div>)}
    {selectedProfile && <FriendProfileModal profile={selectedProfile} online={presence[selectedProfile.id]?.online ?? selectedProfile.is_online} onClose={() => setSelectedProfile(null)} />}
  </section></Layout>
}
