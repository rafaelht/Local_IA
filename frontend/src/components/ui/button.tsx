import { Slot } from '@radix-ui/react-slot'
import type { ComponentPropsWithoutRef, ElementType, ReactNode } from 'react'

interface ButtonProps {
  asChild?: boolean
  children: ReactNode
  className?: string
}

export function Button({ asChild, children, className = '', ...props }: ButtonProps & ComponentPropsWithoutRef<'button'>) {
  const Comp: ElementType = asChild ? Slot : 'button'

  return (
    <Comp
      className={`inline-flex items-center justify-center rounded-2xl bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-400 ${className}`}
      {...props}
    >
      {children}
    </Comp>
  )
}
