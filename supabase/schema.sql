-- ============================================================
--  MovieAlert Supabase Schema
--  Supabase SQL Editor에 전체 붙여넣기 후 실행
-- ============================================================

-- ── 초대 코드 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invite_codes (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  code        TEXT UNIQUE NOT NULL,
  used_by     UUID REFERENCES auth.users(id),
  used_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── 사용자 프로필 ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_profiles (
  id               UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  telegram_chat_id TEXT    DEFAULT '',
  is_active        BOOLEAN DEFAULT true,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── 사용자별 감시 설정 ────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_configs (
  id             UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id        UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
  movies         TEXT[]  DEFAULT '{}',
  branches       TEXT[]  DEFAULT '{}',
  event_labels   TEXT[]  DEFAULT ARRAY['무대인사','GV','시사회'],
  cgv_enabled      BOOLEAN DEFAULT true,
  lotte_enabled    BOOLEAN DEFAULT true,
  megabox_enabled  BOOLEAN DEFAULT true,
  check_days_ahead INTEGER DEFAULT 0,
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── 사용자별 감지 상태 (중복 알림 방지용) ─────────────────
CREATE TABLE IF NOT EXISTS movie_states (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  title       TEXT NOT NULL,
  theater     TEXT NOT NULL,
  branch      TEXT DEFAULT '',
  event_label TEXT DEFAULT '',
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, title, theater, branch, event_label)
);

-- ── 감지 이력 (대시보드 표시용) ───────────────────────────
CREATE TABLE IF NOT EXISTS detected_movies (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  title       TEXT NOT NULL,
  theater     TEXT NOT NULL,
  branch      TEXT DEFAULT '',
  event_label TEXT DEFAULT '',
  booking_url TEXT DEFAULT '',
  detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
--  Row Level Security
-- ============================================================
ALTER TABLE invite_codes    ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles   ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_configs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE movie_states    ENABLE ROW LEVEL SECURITY;
ALTER TABLE detected_movies ENABLE ROW LEVEL SECURITY;

-- 초대 코드: 미사용 코드는 누구나 조회 가능 (회원가입 검증용)
CREATE POLICY "invite_codes_select" ON invite_codes
  FOR SELECT USING (used_by IS NULL);
CREATE POLICY "invite_codes_update" ON invite_codes
  FOR UPDATE USING (used_by IS NULL);

-- 사용자 프로필
CREATE POLICY "profiles_select" ON user_profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "profiles_insert" ON user_profiles FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "profiles_update" ON user_profiles FOR UPDATE USING (auth.uid() = id);

-- 사용자 설정
CREATE POLICY "configs_select" ON user_configs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "configs_insert" ON user_configs FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "configs_update" ON user_configs FOR UPDATE USING (auth.uid() = user_id);

-- 감지 상태 (읽기 + 삭제 — 상태 초기화 버튼용)
CREATE POLICY "states_select" ON movie_states FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "states_delete" ON movie_states FOR DELETE USING (auth.uid() = user_id);

-- 감지 이력 (읽기만)
CREATE POLICY "detections_select" ON detected_movies FOR SELECT USING (auth.uid() = user_id);

-- ============================================================
--  신규 회원가입 시 프로필·설정 자동 생성 트리거
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.user_profiles (id)   VALUES (NEW.id) ON CONFLICT DO NOTHING;
  INSERT INTO public.user_configs (user_id) VALUES (NEW.id) ON CONFLICT DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- ============================================================
--  초대 코드 예시 (관리자가 직접 실행)
--  필요한 만큼 코드를 추가하세요
-- ============================================================
-- INSERT INTO invite_codes (code) VALUES
--   ('MOVIE-AAAA'),
--   ('MOVIE-BBBB'),
--   ('MOVIE-CCCC');
