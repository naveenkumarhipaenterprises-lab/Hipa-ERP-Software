import { createContext } from 'react'

// Context objects live apart from their providers so Fast Refresh keeps working
export const AuthContext = createContext(null)
export const ToastContext = createContext(null)
