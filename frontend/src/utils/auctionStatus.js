// Central place for turning an auction lot's start/end time into a
// live status. We compute this from the clock instead of trusting a
// static "status" field, so cards move between Upcoming -> Live -> Ended
// on their own as time passes.

export function getLiveStatus(lot) {
  const now = Date.now()
  const start = new Date(lot.start_time).getTime()
  const end = new Date(lot.end_time).getTime()
  if (now < start) return 'UPCOMING'
  if (now >= end) return 'ENDED'
  return 'ACTIVE'
}

export function formatCountdown(endTime) {
  const remaining = new Date(endTime) - new Date()
  if (remaining <= 0) return 'Ended'
  const d = Math.floor(remaining / 86400000)
  const h = Math.floor((remaining % 86400000) / 3600000)
  const m = Math.floor((remaining % 3600000) / 60000)
  const s = Math.floor((remaining % 60000) / 1000)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m ${s}s`
  return `${m}m ${s}s`
}

export function formatTimeUntilStart(startTime) {
  const remaining = new Date(startTime) - new Date()
  if (remaining <= 0) return 'starting soon'
  const d = Math.floor(remaining / 86400000)
  const h = Math.floor((remaining % 86400000) / 3600000)
  if (d > 0) return `in ${d}d ${h}h`
  const m = Math.floor((remaining % 3600000) / 60000)
  return `in ${h}h ${m}m`
}

export const statusTagMeta = {
  ACTIVE: { label: 'Live', cls: 'tag-live' },
  UPCOMING: { label: 'Upcoming', cls: 'tag-upcoming' },
  ENDED: { label: 'Ended', cls: 'tag-ended' },
}
