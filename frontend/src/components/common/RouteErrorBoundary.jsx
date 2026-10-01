import { CircleAlert, RefreshCw } from 'lucide-react'
import { Component } from 'react'
import Button from './Button'
import EmptyState from './EmptyState'

/**
 * Catches errors thrown while loading or rendering a page (e.g. a lazy chunk that
 * failed to download after a redeploy) so the layout stays usable instead of blanking.
 * Give it `key={pathname}` so navigating elsewhere clears the error.
 */
export default class RouteErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Page failed to render:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <>
        <title>Page Error | HIPA MASALA</title>
        <EmptyState
        icon={CircleAlert}
        title="This page couldn't be loaded"
        message="Check your connection and reload. If it keeps happening, contact your administrator."
        action={
          <Button icon={RefreshCw} onClick={() => window.location.reload()}>
            Reload Page
          </Button>
          }
        />
      </>
    )
  }
}
