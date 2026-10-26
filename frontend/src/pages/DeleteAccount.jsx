import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { post } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function DeleteAccount() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState(false)

  if (!user) return null

  const handleDelete = async (event) => {
    event.preventDefault()
    if (!window.confirm('Permanently delete your account? This cannot be undone.')) return
    setError('')
    setDeleting(true)
    try {
      await post('/accounts/me/delete/', { password, code })
      window.location.assign('/login')
    } catch (err) {
      setError(err.message)
      setDeleting(false)
    }
  }

  return (
    <Layout>
      <section className="delete-account-page">
        <h2>Delete account</h2>
        <div className="panel delete-account-panel">
          <p>
            This permanently removes your profile and login credentials. Completed auction and
            order records remain anonymous so marketplace history stays accurate.
          </p>
          <p>
            You must first finish or cancel any active auctions, winning bids, or orders.
          </p>
          <form onSubmit={handleDelete}>
            <div className="field">
              <label htmlFor="delete-password">Password</label>
              <input
                id="delete-password"
                className="input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
            {user.has_two_fa && (
              <div className="field">
                <label htmlFor="delete-code">Authenticator or recovery code</label>
                <input
                  id="delete-code"
                  className="input"
                  autoCapitalize="characters"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  required
                />
              </div>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="delete-account-actions">
              <button className="btn btn-outline" type="submit" disabled={deleting}>
                {deleting ? 'Deleting…' : 'Permanently delete'}
              </button>
              <button className="btn btn-ghost" type="button" onClick={() => navigate('/account')}>
                Keep my account
              </button>
            </div>
          </form>
        </div>
      </section>
    </Layout>
  )
}
