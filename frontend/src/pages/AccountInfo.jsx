import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { del, upload } from '../api/client'

export default function AccountInfo() {
  const { user, refreshUser } = useAuth()
  const [avatarFile, setAvatarFile] = useState(null)
  const [avatarPreview, setAvatarPreview] = useState('')
  const [progress, setProgress] = useState(0)
  const [avatarError, setAvatarError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!avatarFile) { setAvatarPreview(''); return undefined }
    const url = URL.createObjectURL(avatarFile); setAvatarPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [avatarFile])
  if (!user) return null

  const chooseAvatar = (event) => {
    const file = event.target.files?.[0] || null
    setAvatarError('')
    if (file && !['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type)) return setAvatarError('Use a JPEG, PNG, WEBP, or GIF image.')
    if (file && file.size > 2 * 1024 * 1024) return setAvatarError('Avatar images must be 2 MB or smaller.')
    setAvatarFile(file)
  }
  const saveAvatar = async () => {
    if (!avatarFile) return
    setBusy(true); setAvatarError(''); setProgress(0)
    try { const body = new FormData(); body.append('avatar', avatarFile); await upload('/accounts/me/avatar/', body, setProgress); await refreshUser(); setAvatarFile(null) } catch (err) { setAvatarError(err.message) } finally { setBusy(false) }
  }
  const removeAvatar = async () => {
    setBusy(true); setAvatarError('')
    try { await del('/accounts/me/avatar/'); await refreshUser(); setAvatarFile(null); setProgress(0) } catch (err) { setAvatarError(err.message) } finally { setBusy(false) }
  }

  return (
    <Layout>
      <section style={{ padding: '30px 0 70px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: 20,
            marginBottom: 34,
          }}
        >
          <h2>Account information</h2>
          {/* <div className="status-badge">{user.role === 'ADMIN' ? 'Administrator · bidding and selling disabled' : 'Bidder and auction organizer'}</div> */}
        </div>

        <div className="account-profile-layout">
        <div className="account-avatar-panel panel">
          <img src={avatarPreview || user.avatar || '/default-avatar.svg'} alt={`${user.username}'s avatar`} />
          <label className="btn btn-outline btn-sm" htmlFor="account-avatar">Choose profile picture</label>
          <input id="account-avatar" className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={chooseAvatar} />
          {avatarFile && <button className="btn btn-primary btn-sm" type="button" disabled={busy} onClick={saveAvatar}>{busy ? `Uploading ${progress}%` : 'Upload avatar'}</button>}
          {user.avatar && <button className="btn btn-ghost btn-sm" type="button" disabled={busy} onClick={removeAvatar}>Remove avatar</button>}
          <small>JPEG, PNG, WEBP or GIF. Maximum 2 MB.</small>
          {avatarError && <p className="form-error" role="alert">{avatarError}</p>}
        </div>
        <div className="form-narrow" style={{ maxWidth: 380, textAlign: 'left' }}>
          <div className="field">
            <label>first name</label>
            <input className="input" defaultValue={user.first_name || ''} disabled />
          </div>
          <div className="field">
            <label>last name</label>
            <input className="input" defaultValue={user.last_name || ''} disabled />
          </div>
          <div className="field">
            <label>username</label>
            <input className="input" defaultValue={user.username} disabled />
          </div>
          <div className="field">
            <label>bio</label>
            <textarea className="textarea" defaultValue={user.bio} disabled />
          </div>
          <div className="field">
            <label>phone number</label>
            <input className="input" defaultValue={user.phone_number} disabled />
          </div>
          <div className="field">
            <label>email</label>
            <input className="input" defaultValue={user.email} disabled />
          </div>
          <Link to="/account/update" className="btn btn-outline">
            update profile
          </Link>
        </div>
        </div>

        {user.role !== 'ADMIN' && (
          <div style={{ marginTop: 60, textAlign: 'right' }}>
            <Link to="/account/delete" className="btn btn-outline">
              delete account
            </Link>
          </div>
        )}
      </section>
    </Layout>
  )
}
