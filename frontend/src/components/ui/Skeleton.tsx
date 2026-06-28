import React from 'react'

interface SkeletonProps {
  count?: number
}

export function Skeleton({ count = 3 }: SkeletonProps) {
  const items = Array.from({ length: count })
  return (
    <div className="space-y-3">
      {items.map((_, i) => (
        <div key={i} className="flex w-full">
          <div className="animate-pulse flex-1">
            <div className="h-3 rounded-full bg-slate-800/60 mb-2 max-w-[40%]" />
            <div className="h-12 rounded-2xl bg-slate-800/60" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default Skeleton
