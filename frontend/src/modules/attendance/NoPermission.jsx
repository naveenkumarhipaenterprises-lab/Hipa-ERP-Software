import { Lock } from 'lucide-react'
import EmptyState from '../../components/common/EmptyState'

/** Shown in place of a section the user has no permission for (the server refuses it anyway). */
export default function NoPermission({ what }) {
  return (
    <EmptyState
      icon={Lock}
      title="You don't have permission for this section"
      message={`Ask an administrator to give you the ${what} permission in Settings → Users.`}
    />
  )
}
