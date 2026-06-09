/**
 * TTS API Service
 * Calls backend edge_tts server for audio with word timings
 */

const API_BASE = '/api/tts'

/**
 * Fetch audio with word timings for synchronized highlighting
 * @param {string} text - Text to synthesize
 * @param {Object} options - Voice options
 * @returns {Promise<{audio: string, words: Array, cached: boolean}>}
 */
export async function fetchWithTiming(text, options = {}) {
  const { voice = 'en-US-AndrewNeural', rate = '+0%', pitch = '+0Hz' } = options

  const response = await fetch(`${API_BASE}/with-timing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice, rate, pitch }),
  })

  if (!response.ok) {
    throw new Error(`TTS API error: ${response.status}`)
  }

  return response.json()
}

/**
 * Get available voices
 * @returns {Promise<{voices: string[]}>}
 */
export async function getVoices() {
  const response = await fetch(`${API_BASE}/voices`)
  if (!response.ok) {
    throw new Error(`Voices API error: ${response.status}`)
  }
  return response.json()
}
