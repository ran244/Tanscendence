import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import RouteLoading from './RouteLoading'

export default function ParticipantRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <RouteLoading message="Checking account role…" />
  if (!user) return <Navigate to="/login" replace />
  if (user.role === 'ADMIN') return <Navigate to="/admin" replace />
  return children
}
