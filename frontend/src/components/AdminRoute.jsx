import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import RouteLoading from './RouteLoading'

export default function AdminRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <RouteLoading message="Loading administrator workspace…" />
  if (!user) return <Navigate to="/login?next=/admin" replace />
  if (user.role !== 'ADMIN') return <Navigate to="/" replace />
  return children
}
