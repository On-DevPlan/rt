import { useState, useRef, useCallback, useEffect } from 'react'
import { fetchWithTiming } from '../services/ttsApi'
import { getCurrentWordIndex } from '../utils/wordHighlighter'

export function useTTS(options = {}) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentWordIndex, setCurrentWordIndex] = useState(-1)
  const [words, setWords] = useState([])
  const [error, setError] = useState(null)

  const audioRef = useRef(null)
  const animationFrameRef = useRef(null)

  const play = useCallback(async (text) => {
    try {
      setError(null)
      stop()

      const data = await fetchWithTiming(text, options)
      const binaryStr = atob(data.audio)
      const bytes = new Uint8Array(binaryStr.length)
      for (let i = 0; i < binaryStr.length; i++) {
        bytes[i] = binaryStr.charCodeAt(i)
      }

      const audioContext = new (window.AudioContext || window.webkitAudioContext)()
      const audioBuffer = await audioContext.decodeAudioData(bytes.buffer)
      const source = audioContext.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioContext.destination)
      audioRef.current = { source, audioContext }
      const wordList = data.words || []
      setWords(wordList)

      const startMs = performance.now()
      source.onended = () => {
        setIsPlaying(false)
        setCurrentWordIndex(-1)
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
        audioContext.close()
      }

      source.start(0)
      setIsPlaying(true)

      const tick = () => {
        if (!audioRef.current) return
        const elapsed = performance.now() - startMs
        const index = getCurrentWordIndex(elapsed, wordList)
        setCurrentWordIndex(prev => prev !== index ? index : prev)
        animationFrameRef.current = requestAnimationFrame(tick)
      }
      animationFrameRef.current = requestAnimationFrame(tick)
    } catch (err) {
      setError(err.message)
      setIsPlaying(false)
    }
  }, [options])

  const stop = useCallback(() => {
    if (audioRef.current) {
      try { audioRef.current.source.stop() } catch {}
      try { audioRef.current.audioContext.close() } catch {}
      audioRef.current = null
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }
    setIsPlaying(false)
    setCurrentWordIndex(-1)
    setWords([])
  }, [])

  useEffect(() => {
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
      if (audioRef.current) {
        try { audioRef.current.source.stop() } catch {}
        try { audioRef.current.audioContext.close() } catch {}
      }
    }
  }, [])

  return { isPlaying, currentWordIndex, words, error, play, stop }
}
