import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME || 'YourMovieAlertBot'
const DEFAULT_EVENT_LABELS = ['무대인사', 'GV', '시사회', '시네마톡']

// 롯데시네마 지역별 지점 프리셋
const LOTTE_REGIONS = {
  '서울': [
    '가산디지털','가양','강동','건대입구','김포공항','노원','도곡','독산',
    '서울대입구','수락산','수유','신대방(구로디지털역)','신도림','신림',
    '에비뉴엘(명동)','영등포','용산','월드타워','은평(롯데몰)','중랑',
    '청량리','합정','홍대입구',
  ],
  '경기/인천': [
    '광교','광명(광명사거리)','광명아울렛','구리아울렛','동탄','라페스타',
    '마석','별내','병점','부천(신중동역)','부평','부평갈산','부평역사',
    '북수원(천천동)','산본피트인','서수원','성남중앙(신흥역)','센트럴락',
    '송탄','수원(수원역)','수지','시화(정왕역)','시흥장현','안산','안산고잔',
    '안성','안양일번가','용인기흥','용인역북','위례','의정부민락','인덕원',
    '인천아시아드','인천터미널','진접','파주롯데아울렛','파주야당','파주운정',
    '판교(창조경제밸리)','평촌(범계역)','하남미사','향남',
  ],
}

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
    if (e.nativeEvent.isComposing) return
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
  const navigate = useNavigate()

  // 설정 상태
  const [movies,    setMovies]   = useState([])
  const [branches,  setBranches] = useState([])
  const [evLabels,  setEvLabels] = useState(DEFAULT_EVENT_LABELS)
  const [lotte,     setLotte]    = useState(true)
  const [megabox,   setMegabox]  = useState(true)
  const [daysAhead,     setDaysAhead]    = useState(0)
  const [checkInterval, setCheckInterval] = useState(5)

  // 텔레그램
  const [chatId,    setChatId]   = useState('')
  const [tgInput,   setTgInput]  = useState('')
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
      setLotte(cfg.lotte_enabled ?? true)
      setMegabox(cfg.megabox_enabled ?? true)
      setDaysAhead(cfg.check_days_ahead ?? 0)
      setCheckInterval(cfg.check_interval_minutes ?? 5)
    }
    if (prof?.telegram_chat_id) {
      setChatId(prof.telegram_chat_id)
      setTgInput(prof.telegram_chat_id)
    }
    setLoading(false)
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
      event_labels:            evLabels,
      lotte_enabled:           lotte,
      megabox_enabled:         megabox,
      check_days_ahead:        daysAhead,
      check_interval_minutes:  checkInterval,
      updated_at:              new Date().toISOString(),
    }).eq('user_id', uid)
    if (error) {
      setSaveMsg('저장 실패: ' + error.message)
      setSaving(false)
      setTimeout(() => setSaveMsg(''), 3000)
    } else {
      setSaving(false)
      navigate('/')
    }
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
            <li>텔레그램 <strong>@userinfobot</strong> 에서 본인 Chat ID 확인</li>
            <li>아래에 Chat ID 입력 후 <strong>저장</strong></li>
          </ol>
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

          {/* 롯데 지역 빠른선택 */}
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
              🎯 롯데시네마 지역 빠른선택
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {Object.entries(LOTTE_REGIONS).map(([region, list]) => {
                const allSelected = list.every(b => branches.includes(b))
                const toggle = () => {
                  if (allSelected) {
                    setBranches(branches.filter(b => !list.includes(b)))
                  } else {
                    const merged = [...branches]
                    list.forEach(b => { if (!merged.includes(b)) merged.push(b) })
                    setBranches(merged)
                  }
                }
                return (
                  <button
                    key={region}
                    type="button"
                    onClick={toggle}
                    style={{
                      padding: '4px 12px',
                      fontSize: 12,
                      borderRadius: 20,
                      border: `1px solid ${allSelected ? 'var(--primary)' : 'var(--border)'}`,
                      background: allSelected ? 'var(--primary)' : 'transparent',
                      color: allSelected ? '#fff' : 'var(--text-muted)',
                      cursor: 'pointer',
                    }}
                  >
                    {allSelected ? '✓ ' : ''}{region} ({list.length})
                  </button>
                )
              })}
              {(LOTTE_REGIONS['서울'].some(b => branches.includes(b)) ||
                LOTTE_REGIONS['경기/인천'].some(b => branches.includes(b))) && (
                <button
                  type="button"
                  onClick={() => setBranches(branches.filter(
                    b => !LOTTE_REGIONS['서울'].includes(b) && !LOTTE_REGIONS['경기/인천'].includes(b)
                  ))}
                  style={{
                    padding: '4px 12px', fontSize: 12, borderRadius: 20,
                    border: '1px solid var(--danger)', background: 'transparent',
                    color: 'var(--danger)', cursor: 'pointer',
                  }}
                >
                  전체 해제
                </button>
              )}
            </div>
          </div>
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

        <div className="form-group">
          <label className="form-label">
            며칠 앞까지 감시할지 &nbsp;
            <span style={{ color: 'var(--primary)', fontWeight: 700 }}>
              {daysAhead === 0 ? '오늘만' : `오늘 포함 ${daysAhead + 1}일 (${daysAhead}일 후까지)`}
            </span>
          </label>
          <input
            type="range"
            min={0} max={14} step={1}
            value={daysAhead}
            onChange={e => setDaysAhead(Number(e.target.value))}
            style={{ padding: 0, cursor: 'pointer', accentColor: 'var(--primary)' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            <span>오늘만</span>
            <span>3일</span>
            <span>7일</span>
            <span>14일</span>
          </div>
          <div className="form-hint">
            지점 설정 시에만 적용됩니다. 날짜가 늘어날수록 체크 시간이 길어집니다.
            무대인사는 3~7일 권장.
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">
            감지 주기 &nbsp;
            <span style={{ color: 'var(--primary)', fontWeight: 700 }}>
              {checkInterval}분마다
            </span>
          </label>
          <input
            type="range"
            min={1} max={60} step={1}
            value={checkInterval}
            onChange={e => setCheckInterval(Number(e.target.value))}
            style={{ padding: 0, cursor: 'pointer', accentColor: 'var(--primary)' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            <span>1분</span>
            <span>10분</span>
            <span>30분</span>
            <span>60분</span>
          </div>
          <div className="form-hint">
            짧을수록 빠르게 감지하지만 서버 부하가 증가합니다.
          </div>
        </div>

      </div>

      {/* ── 영화관 선택 ── */}
      <div className="card">
        <div className="card-title">🏟️ 감시할 영화관</div>
        <div>
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
