import { useNavigate, useSearchParams } from 'react-router-dom'
import { useState } from 'react'
import Logo from '../components/Logo'
import { post } from '../api/client'

export default function ResetPassword() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (password !== confirm) { setError('Passwords do not match.'); return }
    try { await post('/accounts/auth/password/reset/confirm/', { token: params.get('token') || '', new_password: password, new_password_confirm: confirm }); navigate('/reset-done') } catch (err) { setError(err.message) }
  }

  return (
    <div className="auth-page">
      <div className="topbar">
        <Logo to="/login" />
      </div>
      <div className="auth-center">
        <div className="auth-card">
          <p className="auth-title">reset password using email</p>
          <form onSubmit={handleSubmit} className="form-narrow">
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="field">
              <input className="input" type="password" placeholder="new password:" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
            </div>
            <div className="field">
              <input className="input" type="password" placeholder="confirm new pass:" minLength={8} value={confirm} onChange={(event) => setConfirm(event.target.value)} required />
            </div>
            <button className="btn btn-outline btn-block" type="submit" style={{ marginTop: 12 }}>
              Next
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
