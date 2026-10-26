export const ChevronLeft = (props) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" {...props}>
    <path d="M15 6l-6 6 6 6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

export const ChevronRight = (props) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" {...props}>
    <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

export const UserCircle = (props) => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" {...props}>
    <circle cx="12" cy="12" r="9.5" stroke="currentColor" strokeWidth="1.6" />
    <circle cx="12" cy="10" r="3.2" stroke="currentColor" strokeWidth="1.6" />
    <path d="M5.5 18.3c1.3-2.4 3.6-3.6 6.5-3.6s5.2 1.2 6.5 3.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
)

export const CloseIcon = (props) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" {...props}>
    <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
  </svg>
)

export const HomeIcon = (props) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" {...props}>
    <path d="M3.5 11.2 12 4l8.5 7.2V20a1 1 0 0 1-1 1h-5v-6h-5v6h-5a1 1 0 0 1-1-1v-8.8Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
  </svg>
)
