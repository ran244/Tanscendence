import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import RouteLoading from './RouteLoading'

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <RouteLoading />
  if (!user) return <Navigate to="/login" replace />
  return children
}
