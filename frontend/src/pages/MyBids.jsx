import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { useData } from '../context/DataContext'

const outcomeTag = {
  winning: { label: 'Winning', cls: 'tag-live' },
  lost: { label: 'Lost', cls: 'tag-lost' },
}

export default function MyBids() {
  const { bids } = useData()
  const [filter, setFilter] = useState('all')
  const [category, setCategory] = useState('all')
  const categories = [...new Set(bids.map((bid) => bid.lot?.product.category).filter(Boolean))]

  const filtered = useMemo(() => {
    return bids.filter((b) => {
      if (!b.lot) return false
      const matchesFilter =
        filter === 'all' ||
        (filter === 'won' && b.outcome === 'winning') ||
        (filter === 'lost' && b.outcome === 'lost')
      const matchesCategory = category === 'all' || b.lot.product.category === category
      return matchesFilter && matchesCategory
    })
  }, [bids, filter, category])

  return (
    <Layout>
      <section style={{ padding: '30px 0 90px' }}>
        <h2 style={{ marginBottom: 24 }}>My bids</h2>

        <div className="filter-bar">
          {[
            ['all', 'All bids'],
            ['won', 'Won bids'],
            ['lost', 'Lost bids'],
          ].map(([key, label]) => (
            <button
              key={key}
              className={`filter-chip ${filter === key ? 'active' : ''}`}
              onClick={() => setFilter(key)}
            >
              {label}
            </button>
          ))}
          <select
            className="filter-chip input"
            style={{ padding: '9px 14px' }}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="all">All categories</option>
            {categories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state">
            <h3>No bids here yet</h3>
            <p>Adjust the filters or head to the home page to find something worth bidding on.</p>
          </div>
        ) : (
          filtered.map((b) => {
            const tag = outcomeTag[b.outcome]
            return (
              <Link key={b.id} className="list-row bid-history-row" to={`/lots/${b.lot.id}`} aria-label={`Open bid of $${b.amount} on ${b.lot.product.name}`}>
                <img src={b.lot.product.image} alt="" />
                <div className="flex1">
                  <h4>{b.lot.product.name}</h4>
                  <div className="sub">
                    {b.lot.product.category} &middot; bid placed {new Date(b.placed_at).toLocaleDateString()}
                  </div>
                </div>
                <span className="bid-result">
                  <span className={`tag ${tag.cls}`}>{tag.label}</span>
                  <span className="amount">${b.amount}</span>
                </span>
              </Link>
            )
          })
        )}
      </section>
    </Layout>
  )
}
