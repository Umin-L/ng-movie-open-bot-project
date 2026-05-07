import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function ResetPassword() {
  const [password, setPassword]   = useState('')
  const [confirm, setConfirm]     = useState('')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')
  const [success, setSuccess]     = useState('')
  const navigate                  = useNavigate()

  const handleReset = async (e) => {
    e.preventDefault()
    if (password !== confirm) {
      setError('비밀번호가 일치하지 않습니다.')
      return
    }
    setLoading(true); setError('')
    const { error } = await supabase.auth.updateUser({ password })
    if (error) {
      setError(error.message)
    } else {
      setSuccess('비밀번호가 변경되었습니다. 잠시 후 로그인 페이지로 이동합니다.')
      await supabase.auth.signOut()
      setTimeout(() => navigate('/auth'), 2000)
    }
    setLoading(false)
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-title">MovieAlert 🎬</div>
        <div className="auth-subtitle">비밀번호 재설정</div>

        {error   && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {!success && (
          <form onSubmit={handleReset}>
            <div className="form-group">
              <label className="form-label">새 비밀번호</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="8자 이상" minLength={8} required />
            </div>
            <div className="form-group">
              <label className="form-label">비밀번호 확인</label>
              <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                placeholder="비밀번호 재입력" minLength={8} required />
            </div>
            <button type="submit" className="btn-primary" style={{ width:'100%' }} disabled={loading}>
              {loading ? <span className="spinner" /> : '비밀번호 변경'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
