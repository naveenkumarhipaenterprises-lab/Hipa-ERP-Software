import { ClipboardCheck, FlaskConical, PackageCheck, TestTubes } from 'lucide-react'

// Describes the order of work in the lab; contains no business data
const STEPS = [
  { icon: TestTubes, title: 'Sample collection', tone: 'blue' },
  { icon: FlaskConical, title: 'Lab testing', tone: 'purple' },
  { icon: ClipboardCheck, title: 'Result review', tone: 'orange' },
  { icon: PackageCheck, title: 'Batch release', tone: 'green' },
]

export default function LabProcess() {
  return (
    <ol className="lab-process">
      {STEPS.map(({ icon: Icon, title, tone }, i) => (
        <li key={title}>
          <span className={`flow__icon tone-${tone}`} aria-hidden>
            <Icon size={20} />
          </span>
          <span>
            <small>Step {i + 1}</small>
            <strong>{title}</strong>
          </span>
        </li>
      ))}
    </ol>
  )
}
