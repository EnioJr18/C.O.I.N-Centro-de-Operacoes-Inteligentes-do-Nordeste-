import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '../auth/AuthContext'
import { LoginPage } from '../auth/LoginPage'
import { OperationsPage } from '../fleet/OperationsPage'
import { MissionDetailsPage } from '../missions/MissionDetailsPage'
import { MissionFormPage } from '../missions/MissionFormPage'
import { MissionsPage } from '../missions/MissionsPage'
import { DispatchPage } from '../missions/DispatchPage'
import type { ReactNode } from 'react'

function ProtectedPage({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return user && (user.role === 'ADMIN' || user.role === 'OPERADOR') ? children : <Navigate to="/login" replace />
}
export function App() {
  return <AuthProvider><BrowserRouter><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/" element={<ProtectedPage><OperationsPage /></ProtectedPage>} />
    <Route path="/missions" element={<ProtectedPage><MissionsPage /></ProtectedPage>} />
    <Route path="/missions/new" element={<ProtectedPage><MissionFormPage /></ProtectedPage>} />
    <Route path="/missions/dispatch" element={<ProtectedPage><DispatchPage /></ProtectedPage>} />
    <Route path="/missions/:missionId" element={<ProtectedPage><MissionDetailsPage /></ProtectedPage>} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></BrowserRouter></AuthProvider>
}
