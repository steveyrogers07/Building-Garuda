import { useEffect, useRef } from "react"

import type { EgoGraph, GraphNode } from "@/lib/types"

/** Community palette — node colour by Louvain community (design doc §6). */
export const COMMUNITY = [
  "#8fa3bf", "#d98e32", "#7dab77", "#b784c9", "#d9788f",
  "#6fb8ba", "#a3b361", "#c98484", "#7f9bd9", "#c9a227",
]

interface SimNode extends GraphNode {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  col: string
}

/** Dependency-free canvas force layout (ported from client/assets/graph.js):
 *  radius = weighted degree, colour = community, brass double-ring = kingpin.
 *  Hover highlights the neighbourhood; drag re-heats the simulation. */
export function ForceGraph({
  data,
  kingpin,
  onSelect,
}: {
  data: EgoGraph
  kingpin?: string
  onSelect?: (n: GraphNode) => void
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useEffect(() => {
    const canvas = canvasRef.current
    const tip = tipRef.current
    const wrap = wrapRef.current
    if (!canvas || !tip || !wrap) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const dpr = Math.max(1, window.devicePixelRatio || 1)
    let W = 0
    let H = 0
    let raf = 0

    const nodes: SimNode[] = (data.nodes || []).map((n) => ({
      ...n,
      x: 0, y: 0, vx: 0, vy: 0, r: 0, col: "#8fa3bf",
    }))
    const idx: Record<string, number> = {}
    nodes.forEach((n, i) => (idx[n.id] = i))
    const links = (data.edges || [])
      .filter((e) => idx[e.source] != null && idx[e.target] != null)
      .map((e) => ({ s: idx[e.source], t: idx[e.target], w: e.weight || 1 }))

    /* The reveal: siloed grey dots → edges knit in → communities colorize →
     *  the kingpin ring stamps last. Skipped entirely under reduced motion. */
    const REVEAL_MS = 2600
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const t0 = performance.now()
    const SILO = { r: 107, g: 112, b: 106 } // pre-reveal grey
    const phase = (t: number, from: number, to: number) => {
      const p = Math.min(1, Math.max(0, (t - from) / (to - from)))
      return p * p * (3 - 2 * p) // smoothstep
    }
    const hex2rgb = (h: string) => ({
      r: parseInt(h.slice(1, 3), 16),
      g: parseInt(h.slice(3, 5), 16),
      b: parseInt(h.slice(5, 7), 16),
    })

    const maxStr = Math.max(1, ...nodes.map((n) => n.strength || 1))
    nodes.forEach((n) => {
      n.r = 7 + 17 * Math.sqrt((n.strength || 1) / maxStr)
      if (n.id === kingpin) n.r += 4
      n.col = n.community != null ? COMMUNITY[n.community % COMMUNITY.length] : "#8fa3bf"
    })

    function size() {
      const rect = canvas!.getBoundingClientRect()
      W = rect.width
      H = rect.height
      canvas!.width = W * dpr
      canvas!.height = H * dpr
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    size()
    nodes.forEach((n, i) => {
      const a = (i / Math.max(1, nodes.length)) * Math.PI * 2
      n.x = W / 2 + Math.cos(a) * 90 * Math.random() + (Math.random() - 0.5) * 40
      n.y = H / 2 + Math.sin(a) * 90 * Math.random() + (Math.random() - 0.5) * 40
    })

    let alpha = 1
    let hover: number | null = null
    let sel: number | null = null
    let drag: SimNode | null = null
    const adj: Record<number, Record<number, 1>> = {}
    links.forEach((l) => {
      ;(adj[l.s] = adj[l.s] || {})[l.t] = 1
      ;(adj[l.t] = adj[l.t] || {})[l.s] = 1
    })

    function tick() {
      alpha *= 0.985
      if (alpha < 0.02) alpha = 0.02
      const cx = W / 2
      const cy = H / 2
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const d2 = dx * dx + dy * dy || 1
          const f = (2600 * alpha) / d2
          const d = Math.sqrt(d2)
          const fx = (dx / d) * f
          const fy = (dy / d) * f
          a.vx += fx
          a.vy += fy
          b.vx -= fx
          b.vy -= fy
        }
        a.vx += (cx - a.x) * 0.012 * alpha
        a.vy += (cy - a.y) * 0.012 * alpha
      }
      links.forEach((l) => {
        const a = nodes[l.s]
        const b = nodes[l.t]
        const dx = b.x - a.x
        const dy = b.y - a.y
        const d = Math.sqrt(dx * dx + dy * dy) || 1
        const target = 70 + 90 / l.w
        const f = (d - target) * 0.05 * alpha
        const fx = (dx / d) * f
        const fy = (dy / d) * f
        a.vx += fx
        a.vy += fy
        b.vx -= fx
        b.vy -= fy
      })
      nodes.forEach((n) => {
        if (n === drag) return
        n.x += n.vx *= 0.82
        n.y += n.vy *= 0.82
        n.x = Math.max(n.r + 6, Math.min(W - n.r - 6, n.x))
        n.y = Math.max(n.r + 6, Math.min(H - n.r - 6, n.y))
      })
    }

    function draw() {
      ctx!.clearRect(0, 0, W, H)
      const focus = hover != null ? hover : sel
      const t = reduced ? 1 : Math.min(1, (performance.now() - t0) / REVEAL_MS)
      const pEdge = phase(t, 0.18, 0.62) // edges knit the silos together
      const pCol = phase(t, 0.5, 0.86) // then the communities colorize
      const pKing = phase(t, 0.82, 1) // the kingpin ring stamps last

      const shown = Math.ceil(links.length * pEdge)
      for (let li = 0; li < shown; li++) {
        const l = links[li]
        const a = nodes[l.s]
        const b = nodes[l.t]
        const on = focus != null && (l.s === focus || l.t === focus)
        const born = li === shown - 1 && pEdge < 1 ? 0.5 : 1 // newest edge fades in
        ctx!.beginPath()
        ctx!.moveTo(a.x, a.y)
        ctx!.lineTo(b.x, b.y)
        ctx!.strokeStyle = on
          ? "rgba(201,162,39,.6)"
          : `rgba(168,168,158,${(focus != null ? 0.05 : 0.14) * born})`
        ctx!.lineWidth = on ? Math.min(4, 1 + l.w * 0.5) : Math.min(3, 0.6 + l.w * 0.35)
        ctx!.stroke()
      }
      nodes.forEach((n, i) => {
        const dim = focus != null && i !== focus && !adj[focus]?.[i]
        ctx!.globalAlpha = dim ? 0.25 : 1
        if (n.id === kingpin && pKing > 0) {
          ctx!.globalAlpha = (dim ? 0.25 : 1) * pKing
          ctx!.beginPath()
          ctx!.arc(n.x, n.y, n.r + 5 + (1 - pKing) * 10, 0, 7)
          ctx!.strokeStyle = "#c9a227"
          ctx!.lineWidth = 2
          ctx!.stroke()
          ctx!.beginPath()
          ctx!.arc(n.x, n.y, n.r + 9 + (1 - pKing) * 14, 0, 7)
          ctx!.strokeStyle = "rgba(201,162,39,.45)"
          ctx!.lineWidth = 1
          ctx!.stroke()
          ctx!.globalAlpha = dim ? 0.25 : 1
        }
        const c = hex2rgb(n.col)
        const fill = `rgb(${Math.round(SILO.r + (c.r - SILO.r) * pCol)},${Math.round(
          SILO.g + (c.g - SILO.g) * pCol,
        )},${Math.round(SILO.b + (c.b - SILO.b) * pCol)})`
        ctx!.beginPath()
        ctx!.arc(n.x, n.y, n.r, 0, 7)
        ctx!.fillStyle = fill
        ctx!.shadowColor = fill
        ctx!.shadowBlur = i === focus ? 16 : 0
        ctx!.fill()
        ctx!.shadowBlur = 0
        ctx!.lineWidth = 1.5
        ctx!.strokeStyle = "rgba(16,19,24,.55)"
        ctx!.stroke()
        if (n.type === "phone" || n.type === "vehicle") {
          ctx!.fillStyle = "rgba(16,19,24,.9)"
          ctx!.font = `600 ${Math.round(n.r * 0.9)}px 'IBM Plex Mono',monospace`
          ctx!.textAlign = "center"
          ctx!.textBaseline = "middle"
          ctx!.fillText(n.type === "phone" ? "☎" : "⌗", n.x, n.y + 0.5)
        }
        if ((n.id === kingpin && pKing > 0.5) || i === focus || (n.r > 16 && pCol > 0.5)) {
          ctx!.globalAlpha = dim ? 0.25 : 1
          ctx!.fillStyle = "#e9e7e0"
          ctx!.font = "600 11px 'Public Sans',sans-serif"
          ctx!.textAlign = "center"
          ctx!.textBaseline = "top"
          ctx!.fillText(n.label || n.id, n.x, n.y + n.r + 4)
        }
        ctx!.globalAlpha = 1
      })
    }

    function loop() {
      tick()
      draw()
      raf = requestAnimationFrame(loop)
    }
    loop()

    function at(ev: MouseEvent): number | null {
      const rect = canvas!.getBoundingClientRect()
      const mx = ev.clientX - rect.left
      const my = ev.clientY - rect.top
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i]
        if ((mx - n.x) ** 2 + (my - n.y) ** 2 <= (n.r + 3) ** 2) return i
      }
      return null
    }

    function onMove(ev: MouseEvent) {
      const rect = canvas!.getBoundingClientRect()
      if (drag) {
        drag.x = ev.clientX - rect.left
        drag.y = ev.clientY - rect.top
        alpha = Math.max(alpha, 0.3)
        return
      }
      const h = at(ev)
      hover = h
      canvas!.style.cursor = h != null ? "pointer" : "default"
      if (h != null) {
        const n = nodes[h]
        tip!.textContent = `${n.label || n.id} · ${n.type} · str ${n.strength || 0} · ${n.incident_count || 0} incidents`
        tip!.style.left = `${ev.clientX - rect.left + 14}px`
        tip!.style.top = `${ev.clientY - rect.top + 14}px`
        tip!.style.opacity = "1"
      } else {
        tip!.style.opacity = "0"
      }
    }
    function onDown(ev: MouseEvent) {
      const h = at(ev)
      if (h != null) drag = nodes[h]
    }
    function onUp() {
      drag = null
    }
    function onClick(ev: MouseEvent) {
      const h = at(ev)
      sel = h
      if (h != null) onSelectRef.current?.(nodes[h])
    }
    function onLeave() {
      hover = null
      tip!.style.opacity = "0"
    }

    canvas.addEventListener("mousemove", onMove)
    canvas.addEventListener("mousedown", onDown)
    canvas.addEventListener("click", onClick)
    canvas.addEventListener("mouseleave", onLeave)
    window.addEventListener("mouseup", onUp)
    const ro = new ResizeObserver(() => {
      size()
      alpha = Math.max(alpha, 0.4)
    })
    ro.observe(canvas)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      canvas.removeEventListener("mousemove", onMove)
      canvas.removeEventListener("mousedown", onDown)
      canvas.removeEventListener("click", onClick)
      canvas.removeEventListener("mouseleave", onLeave)
      window.removeEventListener("mouseup", onUp)
    }
  }, [data, kingpin])

  return (
    <div ref={wrapRef} className="relative h-full w-full">
      <canvas ref={canvasRef} className="h-full w-full" />
      <div
        ref={tipRef}
        className="pointer-events-none absolute z-10 rounded-md border bg-popover px-2.5 py-1.5 font-mono text-[11px] text-popover-foreground opacity-0 shadow-pop transition-opacity"
      />
    </div>
  )
}
