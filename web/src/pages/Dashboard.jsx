import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'

const THEATER_BADGE = {
  'CGV':    { cls: 'badge-cgv',     icon: '🔴' },
  '롯데시네마': { cls: 'badge-lotte',   icon: '🎯' },
  '메가박스':  { cls: 'badge-megabox', icon: '🟣' },
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const min  = Math.floor(diff / 60000)
  if (min < 1)  return '방금 전'
  if (min < 60) return `${min}분 전`
  const h = Math.floor(min / 60)
  if (h < 24)   return `${h}시간 전`
  return `${Math.floor(h / 24)}일 전`
}

export default function Dashboard({ session }) {
  const [detections, setDetections] = useState([])
  const [profile,    setProfile]    = useState(null)
  const [config,     setConfig]     = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [resetting,  setResetting]  = useState(false)
  const [resetMsg,   setResetMsg]   = useState('')
  const [showConfirm, setShowConfirm] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    const uid = session.user.id

    const [{ data: dets }, { data: prof }, { data: cfg }] = await Promise.all([
      supabase.from('detected_movies')
        .select('*')
        .eq('user_id', uid)
        .order('detected_at', { ascending: false })
        .limit(50),
      supabase.from('user_profiles').select('*').eq('id', uid).single(),
      supabase.from('user_configs').select('*').eq('user_id', uid).single(),
    ])

    setDetections(dets || [])
    setProfile(prof)
    setConfig(cfg)
    setLoading(false)
  }

  async function resetState() {
    setResetting(true)
    setResetMsg('')
    setShowConfirm(false)
    const { error } = await supabase
      .from('movie_states')
      .delete()
      .eq('user_id', session.user.id)
    if (error) {
      setResetMsg('❌ 초기화 실패: ' + error.message)
    } else {
      setResetMsg('✅ 상태 초기화 완료! 다음 체크(최대 5분) 때 현재 열린 예매가 모두 알림으로 옵니다.')
    }
    setResetting(false)
    setTimeout(() => setResetMsg(''), 8000)
  }

  const isTelegramSet = profile?.telegram_chat_id?.trim()
  const watchedMovies = config?.movies?.length ? config.movies.join(', ') : '전체'
  const watchedBranch = config?.branches?.length ? config.branches.join(', ') : '전국'
  const checkInterval = config?.check_interval_minutes ?? 5
  const daysAhead     = config?.check_days_ahead ?? 0

  const watchDates = (() => {
    const fmt   = d => `${d.getMonth() + 1}/${d.getDate()}`
    const today = new Date()
    if (daysAhead === 0) return fmt(today)
    const last = new Date(today); last.setDate(today.getDate() + daysAhead)
    return `${fmt(today)} ~ ${fmt(last)}`
  })()

  // 통계
  const today       = detections.filter(d => new Date(d.detected_at).toDateString() === new Date().toDateString())
  const eventCount  = detections.filter(d => d.event_label).length

  if (loading) {
    return <div style={{ textAlign:'center', padding:'60px' }}><div className="spinner" /></div>
  }

  return (
    <div>
      {/* 확인 모달 */}
      {showConfirm && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200
        }}>
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 14, padding: 32, maxWidth: 360, width: '90%',
            boxShadow: 'var(--shadow)'
          }}>
            <div style={{ fontSize: 32, marginBottom: 12, textAlign: 'center' }}>🔄</div>
            <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8, textAlign: 'center' }}>
              상태 초기화
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 24, textAlign: 'center', lineHeight: 1.6 }}>
              현재 감지된 상태가 모두 지워집니다.<br />
              다음 체크 때 <strong>현재 열려있는 모든 예매</strong>를<br />
              새것으로 인식해 텔레그램 알림을 보냅니다.
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn-ghost" style={{ flex: 1 }}
                onClick={() => setShowConfirm(false)}>취소</button>
              <button className="btn-primary" style={{ flex: 1 }}
                onClick={resetState}>초기화</button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 22, fontWeight: 800 }}>대시보드</h2>
        <button
          className="btn-ghost"
          style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}
          onClick={() => setShowConfirm(true)}
          disabled={resetting}
          title="상태를 초기화하면 현재 열린 예매가 다음 체크 때 모두 알림으로 옵니다"
        >
          {resetting ? <span className="spinner" /> : '🔄'} 상태 초기화
        </button>
      </div>

      {resetMsg && (
        <div className={'alert ' + (resetMsg.startsWith('✅') ? 'alert-success' : 'alert-error')}
          style={{ marginBottom: 16 }}>
          {resetMsg}
        </div>
      )}

      {/* 텔레그램 미설정 경고 */}
      {!isTelegramSet && (
        <div className="alert alert-info" style={{ marginBottom: 20 }}>
          📱 텔레그램이 연결되지 않았습니다. <Link to="/settings">설정</Link>에서 연결해 주세요.
        </div>
      )}

      {/* 감시 현황 요약 */}
      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-number">{detections.length}</div>
          <div className="stat-label">전체 감지</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{today.length}</div>
          <div className="stat-label">오늘 감지</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{eventCount}</div>
          <div className="stat-label">이벤트 감지</div>
        </div>
      </div>

      {/* 감시 설정 요약 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 12 }}>
          <span className="card-title" style={{ marginBottom: 0 }}>현재 감시 설정</span>
          <Link to="/settings" style={{ fontSize: 13, color: 'var(--primary)' }}>수정 →</Link>
        </div>
        <div style={{ display:'flex', flexWrap:'wrap', gap: 16, fontSize: 13 }}>
          <div>
            <span style={{ color:'var(--text-muted)' }}>영화: </span>
            <strong>{watchedMovies}</strong>
          </div>
          <div>
            <span style={{ color:'var(--text-muted)' }}>지점: </span>
            <strong>{watchedBranch}</strong>
          </div>
          <div>
            <span style={{ color:'var(--text-muted)' }}>감지 주기: </span>
            <strong>{checkInterval}분마다</strong>
          </div>
          <div>
            <span style={{ color:'var(--text-muted)' }}>설정 감지일: </span>
            <strong>{watchDates}</strong>
          </div>
          <div>
            <span style={{ color:'var(--text-muted)' }}>텔레그램: </span>
            {isTelegramSet
              ? <span className="connected-badge">✅ 연결됨</span>
              : <span style={{ color:'var(--danger)' }}>미연결</span>
            }
          </div>
        </div>
      </div>

      {/* 감지 이력 */}
      <div className="section-title">최근 감지 이력</div>

      {detections.length === 0 ? (
        <div className="empty-state">
          <div className="icon">🍿</div>
          <p>아직 감지된 영화가 없습니다.</p>
          <p style={{ marginTop: 6 }}>설정에서 감시할 영화를 추가하면<br />예매 오픈 시 텔레그램으로 알림을 받습니다.</p>
        </div>
      ) : (
        <div className="movie-list">
          {detections.map(d => {
            const badge = THEATER_BADGE[d.theater] || { cls: '', icon: '🎬' }
            return (
              <div className="movie-item" key={d.id}>
                <div className="movie-item-left">
                  <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
                    <span className={`badge ${badge.cls}`}>{badge.icon} {d.theater}</span>
                    {d.branch && (
                      <span style={{ fontSize: 12, color:'var(--text-muted)' }}>📍 {d.branch}</span>
                    )}
                    {d.event_label && (
                      <span className="badge badge-event">🎤 {d.event_label}</span>
                    )}
                  </div>
                  <div className="movie-title">{d.title}</div>
                  <div className="movie-meta">
                    <span>🕐 {timeAgo(d.detected_at)}</span>
                    <span>{new Date(d.detected_at).toLocaleString('ko-KR')}</span>
                  </div>
                </div>
                <div className="movie-item-right">
                  {d.booking_url && (
                    <a href={d.booking_url} target="_blank" rel="noreferrer">예매하기</a>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
