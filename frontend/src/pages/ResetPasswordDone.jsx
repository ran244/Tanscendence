import { Link } from 'react-router-dom'
import Logo from '../components/Logo'

export default function ResetPasswordDone() {
  return (
    <div className="auth-page">
      <div className="topbar">
        <Logo to="/login" />
      </div>
      <div className="auth-center">
        <div className="panel" style={{ maxWidth: 380, textAlign: 'center' }}>
          <p style={{ margin: 0, color: 'var(--ink)' }}>
            new pass has been created please login again
          </p>
        </div>
        <Link to="/login" className="btn btn-primary" style={{ marginTop: 26 }}>
          Back to login
        </Link>
      </div>
    </div>
  )
}
