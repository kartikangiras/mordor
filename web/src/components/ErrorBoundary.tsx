import { Component, type ErrorInfo, type ReactNode } from 'react'

type State = { error: Error | null }

/** A crash anywhere renders a readable message with the stack instead of a blank page. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }
  static getDerivedStateFromError(error: Error): State { return { error } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('ui crash', error, info.componentStack) }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="min-h-full bg-ink p-6 font-mono text-xs text-fg">
        <div className="mb-2 text-sm font-semibold text-red-300">The page crashed.</div>
        <pre className="whitespace-pre-wrap text-mute">{String(this.state.error.message || this.state.error)}{'\n'}{this.state.error.stack?.split('\n').slice(1, 6).join('\n')}</pre>
        <button type="button" className="mt-4 h-10 rounded border border-line px-3 text-fg" onClick={() => location.reload()}>reload</button>
      </div>
    )
  }
}

import { isRouteErrorResponse, useRouteError } from 'react-router-dom'

/** errorElement for every route: the same readable panel the boundary shows. */
export function RouteError() {
  const err = useRouteError()
  const notFound = isRouteErrorResponse(err) && err.status === 404
  const msg = isRouteErrorResponse(err) ? `${err.status} ${err.statusText}` : err instanceof Error ? err.message : String(err)
  const stack = err instanceof Error ? err.stack?.split('\n').slice(1, 6).join('\n') : ''
  return (
    <div className="min-h-full bg-ink p-6 font-mono text-xs text-fg">
      <div className="mb-2 text-sm font-semibold text-red-300">{notFound ? 'No such page.' : 'The page crashed.'}</div>
      <pre className="whitespace-pre-wrap text-mute">{msg}{'\n'}{stack}</pre>
      <div className="mt-4 flex gap-2"><button type="button" className="h-10 rounded border border-line px-3 text-fg" onClick={() => location.reload()}>reload</button><a href="/" className="flex h-10 items-center rounded border border-line px-3 text-fg">home</a></div>
    </div>
  )
}
