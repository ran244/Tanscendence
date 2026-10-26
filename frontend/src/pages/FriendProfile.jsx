import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { get, post } from '../api/client'

export default function FriendProfile() {
  const { id } = useParams(); const [profile, setProfile] = useState(null); const [error, setError] = useState(''); const [message, setMessage] = useState('')
  const load = () => get(`/accounts/users/${id}/`).then(setProfile).catch((err) => setError(err.message))
  useEffect(() => { load() }, [id])
  const add = async () => { try { const data = await post('/accounts/friends/request/', { username: profile.username }); setMessage(data.message); load() } catch (err) { setError(err.message) } }
  return <Layout><section className="friend-profile-page">{error && <p role="alert" className="form-error">{error}</p>}{profile && <div className="panel friend-profile-card"><img className="friend-profile-avatar" src={profile.avatar || '/default-avatar.svg'} alt=""/><div><span className={`status-light ${profile.is_online ? 'online' : ''}`} /> {profile.is_online ? 'Online' : 'Offline'}<h2>{profile.username}</h2><p>{profile.bio || 'No biography provided.'}</p><p className="sub">Member since {new Date(profile.date_joined).toLocaleDateString()}</p><div className="friend-profile-actions">{profile.friend_status === 'friends' ? <><Link className="btn btn-primary" to={`/friends/${profile.id}/chat`}>Open chat</Link><Link className="btn btn-outline" to="/friends">Back to friends</Link></> : <button className="btn btn-primary" disabled={profile.friend_status === 'pending_outgoing'} onClick={add}>{profile.friend_status === 'pending_outgoing' ? 'Request sent' : 'Add friend'}</button>}</div>{message && <p role="status">{message}</p>}</div></div>}</section></Layout>
}
