/** Government classification banner - pinned to the top edge of login and
 *  console. Real intel systems carry one; judges should see it immediately. */
export function ClassificationBar() {
  return (
    <div className="flex h-6 w-full items-center justify-center gap-2 overflow-hidden whitespace-nowrap border-b border-brass/25 bg-brass-soft font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-brass sm:tracking-[0.22em]">
      <span className="hidden sm:inline">Restricted · For official use only · Karnataka State Police</span>
      <span className="sm:hidden">Restricted · KSP · Official use only</span>
    </div>
  )
}
