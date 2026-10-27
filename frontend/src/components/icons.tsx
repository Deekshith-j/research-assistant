// Small inline SVG icon set: one 24px grid, 1.6 stroke, round caps, so every icon matches.

import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Icon({ size = 16, children, ...rest }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden {...rest}>
      {children}
    </svg>
  )
}

export const PlusIcon = (p: IconProps) => <Icon {...p}><path d="M12 5v14M5 12h14" /></Icon>
export const CloseIcon = (p: IconProps) => <Icon {...p}><path d="M6 6l12 12M18 6L6 18" /></Icon>
export const TrashIcon = (p: IconProps) => (
  <Icon {...p}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" /></Icon>
)
export const SendIcon = (p: IconProps) => <Icon {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Icon>
export const ChatIcon = (p: IconProps) => (
  <Icon {...p}><path d="M5 5h14a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H10l-4 3v-3H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" /></Icon>
)
export const MemoryIcon = (p: IconProps) => (
  <Icon {...p}><path d="M12 3a6 6 0 0 0-6 6c0 2.3 1.2 3.6 2.2 4.7.6.7 1 1.4 1 2.3V18h5.6v-2c0-.9.4-1.6 1-2.3 1-1.1 2.2-2.4 2.2-4.7a6 6 0 0 0-6-6zM10 21h4" /></Icon>
)
export const DocIcon = (p: IconProps) => (
  <Icon {...p}><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM14 3v5h5M9 13h6M9 17h6" /></Icon>
)
export const EditIcon = (p: IconProps) => <Icon {...p}><path d="M4 20h4L19 9l-4-4L4 16v4zM13 7l4 4" /></Icon>
export const ChevronIcon = (p: IconProps) => <Icon {...p}><path d="M9 6l6 6-6 6" /></Icon>
export const LogoMark = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}><circle cx="11" cy="11" r="6" /><path d="M16 16l4 4M8.5 11h5M11 8.5v5" /></Icon>
)
