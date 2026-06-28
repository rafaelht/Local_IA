import { useCallback, useEffect, useRef, useState } from 'react'

export function useRafState<T>(initialValue: T) {
  const [state, setState] = useState<T>(initialValue)
  const pendingRef = useRef<T>(initialValue)
  const frameRef = useRef<number | null>(null)

  const flushPending = useCallback(() => {
    frameRef.current = null
    setState(pendingRef.current)
  }, [])

  const setRafState = useCallback(
    (next: T | ((current: T) => T)) => {
      const nextValue =
        typeof next === 'function'
          ? (next as (current: T) => T)(pendingRef.current)
          : next

      pendingRef.current = nextValue

      if (frameRef.current === null) {
        frameRef.current = window.requestAnimationFrame(flushPending)
      }
    },
    [flushPending]
  )

  const resetRafState = useCallback(
    (next: T = initialValue) => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current)
        frameRef.current = null
      }
      pendingRef.current = next
      setState(next)
    },
    [initialValue]
  )

  useEffect(
    () => () => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current)
      }
    },
    []
  )

  return [state, setRafState, resetRafState] as const
}
