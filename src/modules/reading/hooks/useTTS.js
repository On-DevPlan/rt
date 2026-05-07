import { useState, useRef, useCallback, useEffect } from 'react'
import { fetchWithTiming } from '../services/ttsApi'
import { getCurrentWordIndex } from '../utils/wordHighlighter'

/**
 * TTS Hook for sentence playback with word-level highlighting
 * @param {Object} options - Voice options
 * @returns {Object} TTS state and controls
 */
export function useTTS(options = {}) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentWordIndex, setCurrentWordIndex] = useState(-1)
  const [words, setWords] = useState([])
  const [error, setError] = useState(null)

  const audioRef = useRef(null)
  const startTimeRef = useRef(null)
  const animationFrameRef = useRef(null)

  const updateCurrentWord = useCallback(() => {
    if (!audioRef.current || !startTimeRef.current || words.length === 0) return

    const elapsed = audioRef.current.currentTime * 1000
    const index = getCurrentWordIndex(elapsed, words)

    if (index !== currentWordIndex) {
      setCurrentWordIndex(index)
    }

    if (!audioRef.current.paused) {
      animationFrameRef.current = requestAnimationFrame(updateCurrentWord)
    }
  }, [words, currentWordIndex])

  const play = useCallback(async (text) => {
    try {
      setError(null)
      stop()

      const data = await fetchWithTiming(text, options)
      const audio = new Audio(`data:audio/mp3;base64,${data.audio}`)
      audioRef.current = audio
      setWords(data.words || [])

      audio.onplay = () => {
        setIsPlaying(true)
        startTimeRef.current = performance.now()
        animationFrameRef.current = requestAnimationFrame(updateCurrentWord)
      }

      audio.onended = () => {
        setIsPlaying(false)
        setCurrentWordIndex(-1)
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current)
        }
      }

      audio.onerror = () => {
        setError('Audio playback failed')
        setIsPlaying(false)
      }

      await audio.play()
    } catch (err) {
      setError(err.message)
      setIsPlaying(false)
    }
  }, [options, updateCurrentWord])

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
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
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
      if (audioRef.current) {
        audioRef.current.pause()
      }
    }
  }, [])

  return {
    isPlaying,
    currentWordIndex,
    words,
    error,
    play,
    stop,
  }
}
