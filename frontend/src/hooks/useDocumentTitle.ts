import { useEffect } from 'react'
import { branding } from '../branding'

export function useDocumentTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title?.trim() ? `${title.trim()} — ${branding.appName}` : branding.appName
    return () => {
      document.title = branding.appName
    }
  }, [title])
}
