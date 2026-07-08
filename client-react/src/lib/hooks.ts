import { useCallback, useEffect, useRef, useState } from "react"
import { ApiError } from "@/lib/api"

interface ApiState<T> {
  data?: T
  error?: ApiError
  loading: boolean
}

/** Fetch-on-mount with cancellation; `reload` refires (used on role switch). */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[]): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ loading: true })
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: undefined }))
    fnRef.current()
      .then((data) => {
        if (alive) setState({ data, loading: false })
      })
      .catch((e: unknown) => {
        if (alive)
          setState({
            error: e instanceof ApiError ? e : new ApiError(0, String(e)),
            loading: false,
          })
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}
