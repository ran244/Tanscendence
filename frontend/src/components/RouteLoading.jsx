import Layout from './Layout'

export default function RouteLoading({ message = 'Loading your account…' }) {
  return (
    <Layout>
      <div className="route-loading" role="status" aria-live="polite">
        {message}
      </div>
    </Layout>
  )
}
