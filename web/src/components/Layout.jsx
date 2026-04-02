import { NavLink, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function Layout({ session, children }) {
  const navigate = useNavigate()

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/auth')
  }

  return (
    <div className="layout">
      <nav className="navbar">
        <span className="navbar-brand">Movie<span>Alert</span> 🎬</span>
        <div className="navbar-nav">
          <NavLink to="/"         className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}>대시보드</NavLink>
          <NavLink to="/settings" className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}>설정</NavLink>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', padding: '0 8px' }}>
            {session.user.email}
          </span>
          <button className="btn-logout" onClick={handleLogout}>로그아웃</button>
        </div>
      </nav>
      <main className="main-content">
        {children}
      </main>
    </div>
  )
}
