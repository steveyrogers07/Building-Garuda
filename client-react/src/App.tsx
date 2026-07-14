import { lazy, Suspense } from "react"
import { HashRouter, Navigate, Route, Routes } from "react-router-dom"

import { ShimmerRows } from "@/components/common/bits"
import { AppShell } from "@/components/layout/AppShell"
import { Toaster } from "@/components/ui/sonner"
import Absconding from "@/pages/Absconding"
import Alerts from "@/pages/Alerts"
import Audit from "@/pages/Audit"
import CaseFile from "@/pages/CaseFile"
import Copilot from "@/pages/Copilot"
import DistrictCommand from "@/pages/DistrictCommand"
import Dossier from "@/pages/Dossier"
import Login from "@/pages/Login"
import MyCases from "@/pages/MyCases"
import Network from "@/pages/Network"
import Overview from "@/pages/Overview"
import SearchPage from "@/pages/SearchPage"

// MapLibre is the heaviest dependency — load it only when the map opens.
const MapView = lazy(() => import("@/pages/MapView"))

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AppShell />}>
          <Route index element={<Overview />} />
          <Route path="my-cases" element={<MyCases />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="district" element={<DistrictCommand />} />
          <Route path="absconding" element={<Absconding />} />
          <Route path="network" element={<Network />} />
          <Route
            path="map"
            element={
              <Suspense fallback={<ShimmerRows n={4} h={90} />}>
                <MapView />
              </Suspense>
            }
          />
          <Route path="copilot" element={<Copilot />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="audit" element={<Audit />} />
          <Route path="case/:id" element={<CaseFile />} />
          <Route path="entity/:id" element={<Dossier />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      <Toaster position="bottom-right" />
    </HashRouter>
  )
}
