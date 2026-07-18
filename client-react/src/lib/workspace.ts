import { useSyncExternalStore } from "react"

/** Investigation workspace tabs - every case/entity the officer opens stays
 *  one click away (IDE-for-investigations, design doc §J2). Session-scoped. */
export interface WorkTab {
  type: "case" | "entity"
  id: string
  title?: string
  icon?: string
}

const KEY = "garuda.tabs"
let tabs: WorkTab[] = load()
const subs = new Set<() => void>()

function load(): WorkTab[] {
  try {
    return (JSON.parse(sessionStorage.getItem(KEY) || "[]") as WorkTab[]) || []
  } catch {
    return []
  }
}

function save() {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(tabs))
  } catch {
    /* session-only */
  }
  subs.forEach((f) => f())
}

export function upsertTab(t: WorkTab) {
  const found = tabs.find((x) => x.type === t.type && x.id === t.id)
  if (!found) {
    tabs = [...tabs, t]
  } else if ((t.title && t.title !== found.title) || (t.icon && t.icon !== found.icon)) {
    tabs = tabs.map((x) =>
      x === found ? { ...x, title: t.title ?? x.title, icon: t.icon ?? x.icon } : x,
    )
  } else {
    return
  }
  save()
}

export function closeTab(type: string, id: string): WorkTab | undefined {
  const i = tabs.findIndex((x) => x.type === type && x.id === id)
  if (i < 0) return undefined
  tabs = tabs.filter((_, j) => j !== i)
  save()
  return tabs[Math.max(0, i - 1)]
}

function subscribe(fn: () => void) {
  subs.add(fn)
  return () => {
    subs.delete(fn)
  }
}

export function useWorkTabs(): WorkTab[] {
  return useSyncExternalStore(subscribe, () => tabs)
}

export function tabRoute(t: WorkTab): string {
  return `/${t.type}/${encodeURIComponent(t.id)}`
}
