/** Government classification banner — pinned to the top edge of login and
 *  console. Real intel systems carry one; judges should see it immediately. */
export function ClassificationBar() {
  return (
    <div className="flex h-6 w-full items-center justify-center gap-2 border-b border-brass/25 bg-brass-soft font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-brass">
      Restricted · For official use only · Karnataka State Police
    </div>
  )
}
