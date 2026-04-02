import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function Auth() {
  const [tab, setTab]           = useState('login')   // 'login' | 'register'
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [inviteCode, setInvite] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [success, setSuccess]   = useState('')
  const navigate                = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true); setError(''); setSuccess('')
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError(error.message)
    else navigate('/')
    setLoading(false)
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setLoading(true); setError(''); setSuccess('')

    // 1. 초대 코드 검증
    const { data: codes, error: codeErr } = await supabase
      .from('invite_codes')
      .select('id, code')
      .eq('code', inviteCode.trim().toUpperCase())
      .is('used_by', null)

    if (codeErr || !codes?.length) {
      setError('유효하지 않은 초대 코드입니다.')
      setLoading(false)
      return
    }

    // 2. 회원가입
    const { data: signupData, error: signupErr } = await supabase.auth.signUp({ email, password })
    if (signupErr) {
      setError(signupErr.message)
      setLoading(false)
      return
    }

    // 3. 초대 코드 사용 처리
    const userId = signupData.user?.id
    if (userId) {
      await supabase
        .from('invite_codes')
        .update({ used_by: userId, used_at: new Date().toISOString() })
        .eq('id', codes[0].id)
    }

    setSuccess('가입이 완료되었습니다! 이메일 인증 후 로그인해 주세요.')
    setLoading(false)
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-title">MovieAlert 🎬</div>
        <div className="auth-subtitle">영화 예매 오픈 알림 서비스</div>

        <div className="auth-tabs">
          <button
            className={'auth-tab' + (tab === 'login' ? ' active' : '')}
            onClick={() => { setTab('login'); setError(''); setSuccess('') }}
          >로그인</button>
          <button
            className={'auth-tab' + (tab === 'register' ? ' active' : '')}
            onClick={() => { setTab('register'); setError(''); setSuccess('') }}
          >회원가입</button>
        </div>

        {error   && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {tab === 'login' ? (
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label className="form-label">이메일</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="your@email.com" required />
            </div>
            <div className="form-group">
              <label className="form-label">비밀번호</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="비밀번호" required />
            </div>
            <button type="submit" className="btn-primary" style={{ width:'100%' }} disabled={loading}>
              {loading ? <span className="spinner" /> : '로그인'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister}>
            <div className="form-group">
              <label className="form-label">초대 코드</label>
              <input type="text" value={inviteCode} onChange={e => setInvite(e.target.value)}
                placeholder="MOVIE-XXXX" required
                style={{ textTransform:'uppercase', letterSpacing:'0.1em' }} />
              <div className="form-hint">관리자에게 초대 코드를 받아 입력하세요.</div>
            </div>
            <div className="form-group">
              <label className="form-label">이메일</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="your@email.com" required />
            </div>
            <div className="form-group">
              <label className="form-label">비밀번호</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="8자 이상" minLength={8} required />
            </div>
            <button type="submit" className="btn-primary" style={{ width:'100%' }} disabled={loading}>
              {loading ? <span className="spinner" /> : '회원가입'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
