import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { supabase } from './lib/supabase'
import Layout from './components/Layout'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import ResetPassword from './pages/ResetPassword'

export default function App() {
  const [session, setSession]       = useState(undefined) // undefined = 로딩 중
  const [isRecovery, setIsRecovery] = useState(false)
  const navigate                    = useNavigate()

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data: listener } = supabase.auth.onAuthStateChange((event, s) => {
      if (event === 'PASSWORD_RECOVERY') {
        setIsRecovery(true)
        setSession(s)
        navigate('/reset-password')
      } else {
        setIsRecovery(false)
        setSession(s)
      }
    })
    return () => listener.subscription.unsubscribe()
  }, [])

  // 세션 로딩 중
  if (session === undefined) {
    return (
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh' }}>
        <div className="spinner" />
      </div>
    )
  }

  // 비밀번호 재설정 중 (이메일 링크 클릭 후)
  if (isRecovery) {
    return (
      <Routes>
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="*" element={<Navigate to="/reset-password" replace />} />
      </Routes>
    )
  }

  if (!session) {
    return (
      <Routes>
        <Route path="/auth" element={<Auth />} />
        <Route path="*" element={<Navigate to="/auth" replace />} />
      </Routes>
    )
  }

  return (
    <Layout session={session}>
      <Routes>
        <Route path="/"          element={<Dashboard session={session} />} />
        <Route path="/settings"  element={<Settings  session={session} />} />
        <Route path="*"          element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}
