import { Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { useState } from 'react'
import Input from '../common/Input'

/** Password field with show/hide toggle and a Caps Lock warning. */
export default function PasswordInput({ label = 'Password', hint, onKeyUp, onBlur, ...rest }) {
  const [visible, setVisible] = useState(false)
  const [capsLock, setCapsLock] = useState(false)

  return (
    <Input
      label={label}
      type={visible ? 'text' : 'password'}
      icon={LockKeyhole}
      hint={capsLock ? 'Caps Lock is on' : hint}
      onKeyUp={(e) => {
        setCapsLock(e.getModifierState?.('CapsLock') ?? false)
        onKeyUp?.(e)
      }}
      onBlur={(e) => {
        setCapsLock(false)
        onBlur?.(e)
      }}
      right={
        <button
          type="button"
          className="icon-btn icon-btn--sm"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
        >
          {visible ? <Eye size={18} /> : <EyeOff size={18} />}
        </button>
      }
      {...rest}
    />
  )
}
