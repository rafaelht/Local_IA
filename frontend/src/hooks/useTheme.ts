import { useEffect } from 'react'
import { useAppStore } from '../store/appStore'

export function useTheme() {
  const theme = useAppStore((state) => state.theme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  return theme
}
