import { KspCrest } from "@/components/brand/KspCrest"

/** Departmental footer for the console.
 *
 *  Two jobs. It gives the console the same government-record framing the login
 *  page already carries - crest, issuing department, statutory notice - so the
 *  product reads as an official system rather than a dashboard.
 *
 *  It also carries the demonstration disclosure into the app itself. Before
 *  this, "Demonstration build on synthetic data" appeared only on Login, so an
 *  evaluator who signed in once and then worked inside the console saw nothing
 *  marking it as a demo. The more official the surface looks, the more that
 *  line has to stay visible - keep it here.
 */
export function OfficialFooter() {
  return (
    <footer className="mt-8 border-t border-line-soft bg-console-deep/40">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col items-center gap-3 px-4 py-5 text-center lg:flex-row lg:items-center lg:justify-between lg:gap-6 lg:px-6 lg:text-left">
        <div className="flex items-center gap-3">
          <KspCrest size={30} withRing={false} className="text-brass/70" />
          <div className="leading-tight">
            <div className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">
              Government of Karnataka · Karnataka State Police
            </div>
            <div className="mt-0.5 font-mono text-[10.5px] tracking-[0.1em] text-faint">
              ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ · State Crime Records Bureau
            </div>
          </div>
        </div>

        <div className="font-mono text-[10.5px] leading-relaxed text-faint lg:text-right">
          Authorized personnel only · Unauthorized access is an offence
          <br />
          Demonstration build on synthetic data · Datathon 2026
        </div>
      </div>
    </footer>
  )
}
