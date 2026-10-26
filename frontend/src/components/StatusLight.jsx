export default function StatusLight({ isSeller }) {
  return (
    <span className={`status-light ${isSeller ? '' : 'bidder-only'}`}>
      <span className="dot" />
      {isSeller ? 'Bidder & Seller' : 'Bidder'}
    </span>
  )
}
