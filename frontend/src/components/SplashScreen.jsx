import logo from '../assets/logo.png'

export default function SplashScreen() {
  return (
    <div className="splash" role="status" aria-live="polite">
      <img src={logo} alt="" />
      <span className="splash-text">ENTERING THE AUCTION HOUSE</span>
    </div>
  )
}
