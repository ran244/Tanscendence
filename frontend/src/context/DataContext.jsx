import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { del, get, post } from '../api/client'
import { useAuth } from './AuthContext'
import { parseMoney } from '../utils/money'

const DataContext = createContext(null)

export function normalizeLot(lot) {
  return { ...lot, current_price: parseMoney(lot.current_price), starting_price: parseMoney(lot.starting_price), minimum_increment: parseMoney(lot.minimum_increment), product: { id: lot.product, name: lot.product_name, description: lot.description || '', category: lot.category?.name || 'Uncategorized', image: lot.product_image || '/placeholder.svg', owner: lot.seller?.username } }
}

export function DataProvider({ children }) {
  const { user, refreshUser, loading: authLoading } = useAuth()
  const [lots, setLots] = useState([])
  const [events, setEvents] = useState([])
  const [bids, setBids] = useState([])
  const [orders, setOrders] = useState([])
  const [savedIds, setSavedIds] = useState(new Set())
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    if (authLoading) return
    try {
      const [lotPage, eventPage] = await Promise.all([get('/auctions/lots/?page_size=100'), get('/auctions/browse/events/?page_size=100')])
      const normalized = (lotPage.results || []).map(normalizeLot)
      setLots(normalized)
      setEvents((eventPage.results || []).map((event) => ({ ...event, lots: event.lots.map(normalizeLot) })))
      if (!user) { setBids([]); setOrders([]); setSavedIds(new Set()); return }
      if (user.role === 'ADMIN') { setBids([]); setOrders([]); setSavedIds(new Set()); return }
      const [bidPage, orderPage, savedPage] = await Promise.all([
        get('/auctions/bids/mine/?page_size=100'),
        get('/orders/?role=buyer&page_size=100'),
        get('/auctions/saved/?page_size=100'),
      ])
      const remainingBidPages = bidPage.total_pages > 1
        ? await Promise.all(Array.from({ length: bidPage.total_pages - 1 }, (_, index) => get(`/auctions/bids/mine/?page_size=100&page=${index + 2}`)))
        : []
      const allBidRows = [bidPage, ...remainingBidPages].flatMap((page) => page.results || [])
      setBids(allBidRows.map((bid) => ({
        ...bid,
        lot: normalizeLot(bid.lot),
        placed_at: bid.created_at,
      })))
      setOrders((orderPage.results || []).map((order) => ({ ...order, lot: normalizeLot(order.lot) })))
      setSavedIds(new Set((savedPage.results || []).map((saved) => saved.lot.id)))
      setError('')
    } catch (err) { setError(err.message) }
  }, [authLoading, user?.id, user?.role, user?.username])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    if (authLoading) return undefined
    let socket
    let retry
    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/browse/`)
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data)
        if (message.type === 'lot.price_update') {
          setLots((previous) => previous.map((lot) => lot.id === Number(message.lot_id) ? { ...lot, current_price: Number(message.current_price), minimum_next_bid: Number(message.minimum_next_bid), bid_count: message.bid_count } : lot))
          setEvents((previous) => previous.map((event) => ({ ...event, lots: event.lots.map((lot) => lot.id === Number(message.lot_id) ? { ...lot, current_price: Number(message.current_price), minimum_next_bid: Number(message.minimum_next_bid), bid_count: message.bid_count } : lot) })))
        } else if (message.type === 'event.activated') refresh()
      }
      socket.onclose = () => { retry = window.setTimeout(connect, 2000) }
    }
    connect()
    return () => { window.clearTimeout(retry); if (socket) { socket.onclose = null; socket.close() } }
  }, [authLoading, refresh])

  const toggleSaved = async (lotId) => {
    if (!user) return
    const saved = savedIds.has(lotId)
    if (saved) await del(`/auctions/lots/${lotId}/saved/`)
    else await post(`/auctions/lots/${lotId}/saved/`)
    setSavedIds((previous) => { const next = new Set(previous); saved ? next.delete(lotId) : next.add(lotId); return next })
  }

  const placeBid = async (lotId, amount) => {
    const current = await refreshUser()
    if (current?.role === 'ADMIN') throw new Error('Administrator accounts cannot place bids.')
    const result = await post(`/auctions/lots/${lotId}/bids/place/`, { amount })
    setLots((previous) => previous.map((lot) => lot.id === lotId ? { ...lot, current_price: Number(result.current_price), bid_count: result.bid_count, minimum_next_bid: Number(result.minimum_next_bid) } : lot))
    setEvents((previous) => previous.map((event) => ({ ...event, lots: event.lots.map((lot) => lot.id === lotId ? { ...lot, current_price: Number(result.current_price), bid_count: result.bid_count, minimum_next_bid: Number(result.minimum_next_bid) } : lot) })))
    return result
  }

  const confirmCod = async (orderId, deliveryDetails) => {
    const payload = typeof deliveryDetails === 'string'
      ? { shipping_address: deliveryDetails }
      : deliveryDetails
    await post(`/orders/${orderId}/confirm-cod/`, payload)
    await refresh()
  }
  const cancelOrder = async (orderId) => { await post(`/orders/${orderId}/cancel/`); await refresh() }
  const savedLots = useMemo(() => lots.filter((lot) => savedIds.has(lot.id)), [lots, savedIds])
  const awaitingPaymentOrders = orders.filter((order) => order.status === 'AWAITING_CONFIRMATION')
  const value = { events, lots, bids, orders, savedLots, awaitingPaymentOrders, error, refresh, isSaved: (lotId) => savedIds.has(lotId), toggleSaved, placeBid, confirmCod, cancelOrder, addLot: async () => { throw new Error('Create the product and event before adding a lot.') } }
  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

export function useData() { return useContext(DataContext) }
