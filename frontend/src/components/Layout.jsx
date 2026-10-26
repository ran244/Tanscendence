import TopBar from './TopBar'
import { useAuth } from '../context/AuthContext'
import SplashScreen from './SplashScreen'
import LiveNotifications from './LiveNotifications'
import SiteFooter from './SiteFooter'

export default function Layout({ children }) {
  const { showSplash } = useAuth()
  return (
    <div className="page">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      {showSplash && <SplashScreen />}
      <LiveNotifications />
      <TopBar />
      <main className="container" id="main-content" tabIndex="-1">{children}</main>
      <SiteFooter />
    </div>
  )
}
