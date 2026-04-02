import { useEffect, useState, useRef } from 'react'
import { supabase } from '../lib/supabase'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME || 'YourMovieAlertBot'
const DEFAULT_EVENT_LABELS = ['무대인사', 'GV', '시사회']

/* ── 태그 입력 컴포넌트 ── */
function TagInput({ value = [], onChange, placeholder }) {
  const [input, setInput] = useState('')
  const ref = useRef()

  const add = () => {
    const v = input.trim()
    if (v && !value.includes(v)) onChange([...value, v])
    setInput('')
  }
  const remove = (tag) => onChange(value.filter(t => t !== tag))
  const onKey = (e) => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() }
    if (e.key === 'Backspace' && !input && value.length) remove(value[value.length - 1])
  }

  return (
    <div className="tag-input-wrap" onClick={() => ref.current?.focus()}>
      {value.map(tag => (
        <span className="tag" key={tag}>
          {tag}
          <span className="tag-remove" onClick={() => remove(tag)}>×</span>
        </span>
      ))}
      <input
        ref={ref}
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={onKey}
        onBlur={add}
        placeholder={value.length === 0 ? placeholder : ''}
      />
    </div>
  )
}

/* ── 토글 컴포넌트 ── */
function Toggle({ id, checked, onChange }) {
  return (
    <label className="toggle">
      <input type="checkbox" id={id} checked={checked} onChange={e => onChange(e.target.checked)} />
      <span className="toggle-track" />
    </label>
  )
}

export default function Settings({ session }) {
  const uid = session.user.id

  // 설정 상태
  const [movies,    setMovies]   = useState([])
  const [branches,  setBranches] = useState([])
  const [evLabels,  setEvLabels] = useState(DEFAULT_EVENT_LABELS)
  const [cgv,       setCgv]      = useState(true)
  const [lotte,     setLotte]    = useState(true)
  const [megabox,   setMegabox]  = useState(true)

  // 텔레그램
  const [chatId,    setChatId]   = useState('')
  const [tgInput,   setTgInput]  = useState('')
  const [tgUsername, setTgUsername] = useState('')
  const [tgLoading, setTgLoading] = useState(false)
  const [tgMsg,     setTgMsg]    = useState('')

  // 저장
  const [saving,    setSaving]   = useState(false)
  const [saveMsg,   setSaveMsg]  = useState('')
  const [loading,   setLoading]  = useState(true)

  useEffect(() => { loadSettings() }, [])

  async function loadSettings() {
    setLoading(true)
    const [{ data: cfg }, { data: prof }] = await Promise.all([
      supabase.from('user_configs').select('*').eq('user_id', uid).single(),
      supabase.from('user_profiles').select('*').eq('id', uid).single(),
    ])
    if (cfg) {
      setMovies(cfg.movies || [])
      setBranches(cfg.branches || [])
      setEvLabels(cfg.event_labels || DEFAULT_EVENT_LABELS)
      setCgv(cfg.cgv_enabled ?? true)
      setLotte(cfg.lotte_enabled ?? true)
      setMegabox(cfg.megabox_enabled ?? true)
    }
    if (prof?.telegram_chat_id) {
      setChatId(prof.telegram_chat_id)
      setTgInput(prof.telegram_chat_id)
    }
    setLoading(false)
  }

  /* 텔레그램 chat_id 자동 조회 (Vercel API 경유) */
  async function fetchChatId() {
    if (!tgUsername.trim()) { setTgMsg('텔레그램 사용자명을 입력해주세요.'); return }
    setTgLoading(true); setTgMsg('')
    try {
      const res  = await fetch(`/api/telegram/get-chat-id?username=${encodeURIComponent(tgUsername.trim().replace('@',''))}`)
      const data = await res.json()
      if (data.chat_id) {
        setTgInput(String(data.chat_id))
        setTgMsg(`✅ Chat ID 찾음: ${data.chat_id}`)
      } else {
        setTgMsg('❌ 찾을 수 없음. 봇에게 /start 를 먼저 보냈는지 확인하세요.')
      }
    } catch {
      setTgMsg('❌ 조회 실패. 잠시 후 다시 시도해주세요.')
    }
    setTgLoading(false)
  }

  /* 텔레그램 연결 저장 */
  async function saveTelegram() {
    setSaving(true)
    const { error } = await supabase.from('user_profiles')
      .update({ telegram_chat_id: tgInput.trim() })
      .eq('id', uid)
    if (!error) { setChatId(tgInput.trim()); setSaveMsg('텔레그램이 연결되었습니다!') }
    else setSaveMsg('저장 실패: ' + error.message)
    setSaving(false)
    setTimeout(() => setSaveMsg(''), 3000)
  }

  /* 영화 감시 설정 저장 */
  async function saveConfig() {
    setSaving(true); setSaveMsg('')
    const { error } = await supabase.from('user_configs').update({
      movies,
      branches,
      event_labels: evLabels,
      cgv_enabled:  cgv,
      lotte_enabled: lotte,
      megabox_enabled: megabox,
      updated_at: new Date().toISOString(),
    }).eq('user_id', uid)
    setSaveMsg(error ? '저장 실패: ' + error.message : '✅ 설정이 저장되었습니다.')
    setSaving(false)
    setTimeout(() => setSaveMsg(''), 3000)
  }

  if (loading) {
    return <div style={{ textAlign:'center', padding:'60px' }}><div className="spinner" /></div>
  }

  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 24 }}>설정</h2>

      {saveMsg && (
        <div className={'alert ' + (saveMsg.startsWith('✅') ? 'alert-success' : 'alert-error')}
          style={{ marginBottom: 20 }}>
          {saveMsg}
        </div>
      )}

      {/* ── 텔레그램 연결 ── */}
      <div className="card">
        <div className="card-title">📱 텔레그램 알림 연결</div>

        {chatId ? (
          <div style={{ marginBottom: 16 }}>
            <span className="connected-badge">✅ 연결됨 (Chat ID: {chatId})</span>
          </div>
        ) : (
          <div className="alert alert-info" style={{ marginBottom: 16 }}>
            아직 텔레그램이 연결되지 않았습니다.
          </div>
        )}

        <div className="telegram-box">
          <div className="tg-title">📋 연결 방법</div>
          <ol>
            <li>텔레그램에서 <strong>@{BOT_USERNAME}</strong> 검색</li>
            <li>봇에게 <strong>/start</strong> 메시지 전송</li>
            <li>아래에 텔레그램 사용자명 입력 후 <strong>Chat ID 자동 조회</strong> 클릭</li>
            <li>조회된 Chat ID 확인 후 <strong>저장</strong></li>
          </ol>
        </div>

        <div className="form-group">
          <label className="form-label">텔레그램 사용자명 (@ 없이)</label>
          <div className="form-row">
            <input
              type="text"
              value={tgUsername}
              onChange={e => setTgUsername(e.target.value)}
              placeholder="예: honggildong"
            />
            <button
              className="btn-ghost"
              style={{ whiteSpace:'nowrap', minWidth: 140 }}
              onClick={fetchChatId}
              disabled={tgLoading}
            >
              {tgLoading ? <span className="spinner" /> : 'Chat ID 자동 조회'}
            </button>
          </div>
          {tgMsg && <div className={`form-${tgMsg.startsWith('✅') ? 'hint' : 'error'}`} style={{ marginTop: 6 }}>{tgMsg}</div>}
        </div>

        <div className="form-group">
          <label className="form-label">Chat ID</label>
          <div className="form-row">
            <input
              type="text"
              value={tgInput}
              onChange={e => setTgInput(e.target.value)}
              placeholder="자동 조회되거나 직접 입력"
            />
            <button
              className="btn-primary"
              style={{ whiteSpace:'nowrap', minWidth: 80 }}
              onClick={saveTelegram}
              disabled={saving || !tgInput.trim()}
            >
              {saving ? <span className="spinner" /> : '저장'}
            </button>
          </div>
          <div className="form-hint">
            자동 조회가 안 될 경우: 봇에게 /start 후 직접 입력하세요.
          </div>
        </div>
      </div>

      {/* ── 감시 영화 설정 ── */}
      <div className="card">
        <div className="card-title">🎬 감시 영화 설정</div>

        <div className="form-group">
          <label className="form-label">감시할 영화 제목 키워드</label>
          <TagInput
            value={movies}
            onChange={setMovies}
            placeholder="영화명 입력 후 Enter (비우면 전체 감시)"
          />
          <div className="form-hint">부분 일치 — 예: "코난" 입력 시 "명탐정 코난" 포함 감지</div>
        </div>

        <div className="form-group">
          <label className="form-label">감시할 지점 키워드</label>
          <TagInput
            value={branches}
            onChange={setBranches}
            placeholder="지점명 입력 후 Enter (비우면 전국)"
          />
          <div className="form-hint">예: 코엑스, 강남, 홍대, 월드타워</div>
        </div>

        <div className="form-group">
          <label className="form-label">감시할 이벤트 라벨</label>
          <TagInput
            value={evLabels}
            onChange={setEvLabels}
            placeholder="이벤트명 입력 (비우면 이벤트 미감시)"
          />
          <div className="form-hint">무대인사, GV, 시사회 등 — 비워두면 일반 상영만 감시</div>
        </div>
      </div>

      {/* ── 영화관 선택 ── */}
      <div className="card">
        <div className="card-title">🏟️ 감시할 영화관</div>
        <div>
          <div className="toggle-row">
            <div>
              <div className="toggle-label">🔴 CGV</div>
              <div className="toggle-desc">Playwright 기반 크롤링 (다소 느림)</div>
            </div>
            <Toggle id="cgv" checked={cgv} onChange={setCgv} />
          </div>
          <div className="toggle-row">
            <div>
              <div className="toggle-label">🎯 롯데시네마</div>
              <div className="toggle-desc">공식 API 기반</div>
            </div>
            <Toggle id="lotte" checked={lotte} onChange={setLotte} />
          </div>
          <div className="toggle-row">
            <div>
              <div className="toggle-label">🟣 메가박스</div>
              <div className="toggle-desc">공식 API 기반 (이벤트 라벨 정확도 높음)</div>
            </div>
            <Toggle id="megabox" checked={megabox} onChange={setMegabox} />
          </div>
        </div>
      </div>

      <button
        className="btn-primary"
        style={{ width:'100%', padding:'14px', fontSize: 16 }}
        onClick={saveConfig}
        disabled={saving}
      >
        {saving ? <span className="spinner" /> : '설정 저장'}
      </button>
    </div>
  )
}
