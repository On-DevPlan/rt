import { useEffect } from 'react'

export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} | RT Framework Registry` : 'RT Framework Registry'
  }, [title])
}
