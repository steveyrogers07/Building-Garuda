import { cn } from "@/lib/utils"

/** Karnataka State Police crest — a geometric Gandaberunda (the two-headed
 *  eagle of Karnataka) in a ringed badge. Single-colour, scales from favicon
 *  to login hero; colour follows `currentColor` so themes recolour it. */
export function KspCrest({
  size = 40,
  withRing = true,
  className,
}: {
  size?: number
  withRing?: boolean
  className?: string
}) {
  return (
    <svg
      viewBox="0 0 240 240"
      width={size}
      height={size}
      className={cn("shrink-0", className)}
      role="img"
      aria-label="Karnataka State Police crest"
      fill="currentColor"
    >
      {withRing && (
        <>
          <circle cx="120" cy="120" r="114" fill="none" stroke="currentColor" strokeWidth="3" />
          <circle cx="120" cy="120" r="106" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6" />
          {/* separator stars at the ring's equator */}
          <path d="M 14 120 l 5 -5 5 5 -5 5 Z" />
          <path d="M 216 120 l 5 -5 5 5 -5 5 Z" />
        </>
      )}

      {/* crown between the two heads */}
      <path d="M 106 66 L 106 52 L 113 60 L 120 46 L 127 60 L 134 52 L 134 66 Z" />

      {/* right half of the Gandaberunda; left is the mirror */}
      <g id="ksp-half">
        {/* neck + outward-facing head + beak */}
        <path d="M 124 112 C 122 98 128 86 141 80 C 147 77 154 78 158 82 C 163 87 163 94 158 99 C 154 103 148 104 143 101 C 137 108 134 116 134 124 Z" />
        <path d="M 158 84 L 176 90 L 158 97 Z" />
        {/* stepped heraldic wing */}
        <path d="M 130 112 C 146 96 170 86 200 82 L 191 102 L 201 106 L 186 128 L 194 133 L 176 152 L 182 158 L 158 166 L 136 154 Z" />
        {/* wing feather separations (negative space) */}
        <path d="M 136 146 L 186 104" stroke="#080d18" strokeWidth="3" fill="none" opacity="0.85" />
        <path d="M 138 152 L 180 130" stroke="#080d18" strokeWidth="3" fill="none" opacity="0.85" />
        {/* talon */}
        <path d="M 128 176 L 140 190 L 132 191 L 137 199 L 128 195 Z" />
      </g>
      <use href="#ksp-half" transform="matrix(-1 0 0 1 240 0)" />

      {/* body + chest */}
      <path d="M 120 100 C 133 100 138 116 138 134 C 138 156 131 170 120 176 C 109 170 102 156 102 134 C 102 116 107 100 120 100 Z" />
      {/* chest chevrons (negative space) */}
      <path d="M 106 128 Q 120 136 134 128" stroke="#080d18" strokeWidth="3" fill="none" opacity="0.85" />
      <path d="M 107 142 Q 120 150 133 142" stroke="#080d18" strokeWidth="3" fill="none" opacity="0.85" />
      {/* fan tail */}
      <path d="M 120 172 L 141 198 L 130 196 L 134 208 L 120 202 L 106 208 L 110 196 L 99 198 Z" />
      {/* eyes (negative space) */}
      <circle cx="146" cy="88" r="2.6" fill="#080d18" />
      <circle cx="94" cy="88" r="2.6" fill="#080d18" />
    </svg>
  )
}

/** Crest + wordmark lockup used in the sidebar and PDF headers. */
export function KspWordmark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <KspCrest size={compact ? 34 : 42} className="text-amber" />
      <div className="min-w-0 leading-tight">
        <div className="font-mono text-[17px] font-bold tracking-[0.22em] text-foreground">
          GARUDA
        </div>
        {!compact && (
          <div className="k-label mt-0.5 whitespace-nowrap text-muted-foreground">
            Karnataka State Police · SCRB
          </div>
        )}
      </div>
    </div>
  )
}
