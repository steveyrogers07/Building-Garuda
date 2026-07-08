/** Government classification banner — pinned to the top edge of login and
 *  console. Real intel systems carry one; judges should see it immediately. */
export function ClassificationBar() {
  return (
    <div className="flex h-6 w-full items-center justify-center gap-2 border-b border-amber/30 bg-amber-soft font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-amber">
      Restricted · For official use only · Karnataka State Police
    </div>
  )
}
