import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'

export default function UpdateInfo() {
  const { user, updateProfile } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    phone_number: user?.phone_number || '',
    bio: user?.bio || '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  if (!user) return null

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setPhone = (e) => {
    const value = e.target.value
    if (/^\+?[0-9]*$/.test(value)) {
      setForm((current) => ({ ...current, phone_number: value }))
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      await updateProfile(form)
      navigate('/account')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
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
          <h2>Update info</h2>
          {/* <div className="status-badge">{user.role === 'ADMIN' ? 'Administrator · bidding and selling disabled' : 'Bidder and auction organizer'}</div> */}
        </div>

        <form onSubmit={handleSave} className="form-narrow" style={{ maxWidth: 380, textAlign: 'left' }}>
          <div className="field">
            <label htmlFor="first-name">first name</label>
            <input
              id="first-name"
              className="input"
              value={form.first_name}
              onChange={set('first_name')}
            />
          </div>
          <div className="field">
            <label htmlFor="last-name">last name</label>
            <input
              id="last-name"
              className="input"
              value={form.last_name}
              onChange={set('last_name')}
            />
          </div>
          <div className="field">
            <label htmlFor="phone-number">phone number</label>
            <input
              id="phone-number"
              className="input"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              maxLength={20}
              pattern="\+?[0-9]+"
              title="Use digits only, optionally beginning with +."
              placeholder="+962700000000"
              value={form.phone_number}
              onChange={setPhone}
            />
            <small>Digits only, with an optional + at the beginning.</small>
          </div>
          <div className="field">
            <label htmlFor="profile-bio">bio</label>
            <textarea id="profile-bio" className="textarea" value={form.bio} onChange={set('bio')} />
          </div>
          <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
            <button type="button" className="btn btn-ghost" onClick={() => navigate('/account')}>
              cancel
            </button>
            <button type="submit" className="btn btn-outline" disabled={saving}>
              {saving ? 'saving…' : 'save changes'}
            </button>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>
      </section>
    </Layout>
  )
}
