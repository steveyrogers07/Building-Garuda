import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "@fontsource/saira-condensed/500.css"
import "@fontsource/saira-condensed/600.css"
import "@fontsource/saira-condensed/700.css"
import "@fontsource/public-sans/400.css"
import "@fontsource/public-sans/500.css"
import "@fontsource/public-sans/600.css"
import "@fontsource/ibm-plex-mono/400.css"
import "@fontsource/ibm-plex-mono/500.css"
import "@fontsource/ibm-plex-mono/600.css"
import "./index.css"

import App from "./App"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

/** Dismiss the boot splash (index.html) now that React has painted. */
function dismissBootSplash() {
  document.getElementById("garuda-boot")?.classList.add("gb-done")
}

// Two independent triggers, because neither is sufficient alone.
//
// The double rAF is the accurate one: the first frame only guarantees the
// commit is scheduled, the second that it has actually rendered, so the splash
// never lifts on an empty console. But rAF is tied to compositing and does not
// fire at all in a tab that is not being drawn - open the link in a background
// tab, which is exactly what a middle-click does, and it never runs. Caught by
// measuring: React had rendered 25s earlier and the class was still not set.
//
// The timer covers that case, since timers fire regardless of visibility.
// Whichever wins, adding the class twice is a no-op.
requestAnimationFrame(() => requestAnimationFrame(dismissBootSplash))
setTimeout(dismissBootSplash, 150)

// index.html also dismisses from CSS at 3s regardless. That is the failsafe,
// not the plan - the splash lives outside #root, so if none of this ran it
// would hide the whole app. All of it is best-effort by design.
