import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '../auth/AuthContext'
import { LoginPage } from '../auth/LoginPage'
import { OperationsPage } from '../fleet/OperationsPage'

function ProtectedOperations() {
  const { user } = useAuth()
  return user && (user.role === 'ADMIN' || user.role === 'OPERADOR') ? <OperationsPage /> : <Navigate to="/login" replace />
}
export function App() {
  return <AuthProvider><BrowserRouter><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/" element={<ProtectedOperations />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></BrowserRouter></AuthProvider>
}
