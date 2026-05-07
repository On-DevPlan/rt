/**
 * Word Highlighter Utility
 * Calculates which word should be highlighted based on playback time
 */

/**
 * Get the current word index based on elapsed time
 * @param {number} elapsedMs - Current playback time in milliseconds
 * @param {Array<{text: string, offset: number, duration: number}>} words - Word timings
 * @returns {number} - Index of current word, or -1 if before first word
 */
export function getCurrentWordIndex(elapsedMs, words) {
  if (!words || words.length === 0) return -1

  for (let i = 0; i < words.length; i++) {
    const word = words[i]
    const startMs = word.offset
    const endMs = startMs + word.duration

    if (elapsedMs >= startMs && elapsedMs < endMs) {
      return i
    }
  }

  // After last word
  if (elapsedMs >= words[words.length - 1].offset + words[words.length - 1].duration) {
    return words.length - 1
  }

  return -1
}

/**
 * Split text into word tokens for highlighting
 * @param {string} text - Sentence text
 * @returns {Array<{word: string, isPunctuation: boolean}>}
 */
export function tokenizeText(text) {
  return text.split(/\s+/).map(word => ({
    word,
    isPunctuation: /^[.,!?;:'"()-]+$/.test(word),
  }))
}
