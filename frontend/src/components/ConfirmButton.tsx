// Two-step destructive action without a browser popup: the first click asks
// "Sure?" inline, the second click confirms. It resets after a few seconds.

import { useEffect, useState, type ReactNode } from 'react'

interface Props {
  onConfirm: () => void
  children: ReactNode          // idle content (label and/or icon)
  confirmLabel?: string        // text shown while waiting for confirmation
  className?: string
  title?: string
}

export default function ConfirmButton({ onConfirm, children, confirmLabel = 'Confirm', className = '', title }: Props) {
  const [armed, setArmed] = useState(false)

  // Disarm automatically so a stray earlier click can't confirm later.
  useEffect(() => {
    if (!armed) return
    const t = setTimeout(() => setArmed(false), 4000)
    return () => clearTimeout(t)
  }, [armed])

  return (
    <button
      type="button"
      title={armed ? 'Click again to confirm' : title}
      aria-label={armed ? confirmLabel : title}
      className={`${className} ${armed ? 'armed' : ''}`}
      onClick={e => {
        e.stopPropagation()
        if (armed) { setArmed(false); onConfirm() } else setArmed(true)
      }}
      onBlur={() => setArmed(false)}
    >
      {armed ? confirmLabel : children}
    </button>
  )
}
