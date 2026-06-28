import type { ComponentPropsWithoutRef, ReactNode } from 'react'

interface CardProps extends ComponentPropsWithoutRef<'div'> {
  children: ReactNode
}

export function Card({ children, className = '', ...props }: CardProps) {
  return (
    <div
      className={`rounded-3xl border border-slate-700 bg-slate-900/80 p-5 shadow-[0_25px_80px_rgba(15,23,42,0.35)] ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
