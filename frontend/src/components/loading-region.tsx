import React from "react"

interface LoadingRegionProps {
  loading: boolean
  children: React.ReactNode
  label?: string
}

/**
 * Wraps async content with aria-live="polite" and aria-busy.
 * Screen readers announce when content finishes loading.
 *
 * Usage: wrap <DataTable loading={loading} ...> with this component.
 * Scope to the content area only — do NOT wrap the full page layout.
 */
export function LoadingRegion({
  loading,
  children,
  label = "Content region",
}: LoadingRegionProps) {
  return (
    <div
      aria-live="polite"
      aria-busy={loading}
      aria-label={label}
    >
      {children}
    </div>
  )
}
