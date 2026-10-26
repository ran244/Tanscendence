import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function LiveNotifications() {
  const { user } = useAuth()
  const userId = user?.id
  const [message, setMessage] = useState(null)
  useEffect(() => {
    if (!userId) return
    let socket; let retry; let heartbeat
    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/auth/`)
      socket.onopen = () => { heartbeat = window.setInterval(() => socket.send(JSON.stringify({ type: 'presence.heartbeat' })), 30000) }
      socket.onmessage = (event) => { const payload = JSON.parse(event.data); if (['notification.created', 'lot.alert'].includes(payload.type)) { setMessage(payload.notification || payload); window.setTimeout(() => setMessage(null), 6000) } }
      socket.onclose = () => { window.clearInterval(heartbeat); retry = window.setTimeout(connect, 2000) }
    }
    connect()
    return () => { window.clearTimeout(retry); window.clearInterval(heartbeat); if (socket) { socket.onclose = null; socket.close() } }
  }, [userId])
  if (!message) return null
  const winner = message.event === 'winner' || message.verb === 'LOT_WINNER'
  return <div className={`live-toast ${winner ? 'winner-toast' : ''}`} role="status" aria-live="polite">
    {winner && <div className="confetti" aria-hidden="true">{Array.from({ length: 18 }, (_, index) => <i key={index} />)}</div>}
    <strong>{winner ? 'Congratulations — you won!' : (message.verb || message.alert || 'Auction update').replaceAll('_', ' ')}</strong>
    {winner && <a href="/orders">Complete your order</a>}
    <button aria-label="Dismiss notification" onClick={() => setMessage(null)}>×</button>
  </div>
}
