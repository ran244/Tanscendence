import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Login from './pages/Login'
import Signup from './pages/Signup'
import CheckEmail from './pages/CheckEmail'
import VerifyEmail from './pages/VerifyEmail'
import AccountInfo from './pages/AccountInfo'
import UpdateInfo from './pages/UpdateInfo'
import DeleteAccount from './pages/DeleteAccount'
import Wallet from './pages/Wallet'
import MyBids from './pages/MyBids'
import LotBidPage from './pages/LotBidPage'
import MyAuctions from './pages/MyAuctions'
import OrderHistory from './pages/OrderHistory'
import OrderDetail from './pages/OrderDetail'
import SavedItems from './pages/SavedItems'
import ReportIssue from './pages/ReportIssue'
import CreateAuctionPage from './pages/CreateAuctionPage'
import Cart from './pages/Cart'
import TwoFactor from './pages/TwoFactor'
import Notifications from './pages/Notifications'
import AdminDashboard from './pages/AdminDashboard'
import Analytics from './pages/Analytics'
import Privacy from './pages/Privacy'
import Terms from './pages/Terms'
import About from './pages/About'
import Sales from './pages/Sales'
import Security from './pages/Security'
import DeveloperApi from './pages/DeveloperApi'
import BulkImport from './pages/BulkImport'
import Friends from './pages/Friends'
import FriendProfile from './pages/FriendProfile'
import FriendChat from './pages/FriendChat'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import ParticipantRoute from './components/ParticipantRoute'
import ScrollToTop from './components/ScrollToTop'

export default function App() {
  return (
    <>
    <ScrollToTop />
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/login/2fa" element={<TwoFactor />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/signup/check-email" element={<CheckEmail />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

      <Route path="/account" element={<ProtectedRoute><AccountInfo /></ProtectedRoute>} />
      <Route path="/account/update" element={<ProtectedRoute><UpdateInfo /></ProtectedRoute>} />
      <Route path="/account/delete" element={<ParticipantRoute><DeleteAccount /></ParticipantRoute>} />

      <Route path="/wallet" element={<ProtectedRoute><Wallet /></ProtectedRoute>} />
      <Route path="/my-bids" element={<ParticipantRoute><MyBids /></ParticipantRoute>} />
      <Route path="/lots/:id" element={<ParticipantRoute><LotBidPage /></ParticipantRoute>} />
      <Route path="/my-auctions" element={<ParticipantRoute><MyAuctions /></ParticipantRoute>} />
      <Route path="/orders" element={<ParticipantRoute><OrderHistory /></ParticipantRoute>} />
      <Route path="/orders/:id" element={<ParticipantRoute><OrderDetail /></ParticipantRoute>} />
      <Route path="/saved" element={<ParticipantRoute><SavedItems /></ParticipantRoute>} />
      <Route path="/report-issue" element={<ProtectedRoute><ReportIssue /></ProtectedRoute>} />
      <Route path="/create-auction" element={<ParticipantRoute><CreateAuctionPage /></ParticipantRoute>} />
      <Route path="/auctions/:id/edit" element={<ParticipantRoute><CreateAuctionPage /></ParticipantRoute>} />
      <Route path="/cart" element={<ProtectedRoute><Cart /></ProtectedRoute>} />
      <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
      <Route path="/analytics" element={<ProtectedRoute><Analytics /></ProtectedRoute>} />
      <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
      <Route path="/admin-dashboard" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/about" element={<About />} />
      <Route path="/sales" element={<ProtectedRoute><Sales /></ProtectedRoute>} />
      <Route path="/security" element={<ProtectedRoute><Security /></ProtectedRoute>} />
      <Route path="/developer-api" element={<ProtectedRoute><DeveloperApi /></ProtectedRoute>} />
      <Route path="/bulk-import" element={<ParticipantRoute><BulkImport /></ParticipantRoute>} />
      <Route path="/friends" element={<ProtectedRoute><Friends /></ProtectedRoute>} />
      <Route path="/friends/:id" element={<ProtectedRoute><FriendProfile /></ProtectedRoute>} />
      <Route path="/friends/:id/chat" element={<ProtectedRoute><FriendChat /></ProtectedRoute>} />

      <Route path="*" element={<Home />} />
    </Routes>
    </>
  )
}
