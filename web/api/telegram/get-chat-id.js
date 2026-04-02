/**
 * Vercel Serverless Function
 * GET /api/telegram/get-chat-id?username=홍길동텔레그램아이디
 *
 * 봇에게 /start 를 보낸 사용자의 chat_id 를 반환한다.
 * 환경변수: TELEGRAM_BOT_TOKEN (Vercel 프로젝트 설정에서 추가)
 */
export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*')
  if (req.method === 'OPTIONS') return res.status(200).end()

  const { username } = req.query
  if (!username) {
    return res.status(400).json({ error: 'username 파라미터가 필요합니다.' })
  }

  const token = process.env.TELEGRAM_BOT_TOKEN
  if (!token) {
    return res.status(500).json({ error: 'TELEGRAM_BOT_TOKEN 환경변수가 없습니다.' })
  }

  try {
    // 최근 100개 업데이트에서 해당 username 찾기
    const url  = `https://api.telegram.org/bot${token}/getUpdates?limit=100&allowed_updates=["message"]`
    const resp = await fetch(url)
    const data = await resp.json()

    if (!data.ok) {
      return res.status(502).json({ error: '텔레그램 API 오류', detail: data.description })
    }

    const target = username.toLowerCase().replace('@', '')
    let chatId = null

    for (const update of (data.result || []).reverse()) {
      const from = update.message?.from
      if (!from) continue
      if (from.username?.toLowerCase() === target) {
        chatId = update.message.chat.id
        break
      }
    }

    if (chatId) {
      return res.status(200).json({ chat_id: chatId })
    } else {
      return res.status(200).json({ chat_id: null })
    }
  } catch (err) {
    return res.status(500).json({ error: '서버 오류', detail: err.message })
  }
}
