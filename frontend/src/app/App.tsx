import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '../auth/AuthContext'
import { LoginPage } from '../auth/LoginPage'
import { OperationsPage } from '../fleet/OperationsPage'
import { MissionDetailsPage } from '../missions/MissionDetailsPage'
import { MissionFormPage } from '../missions/MissionFormPage'
import { MissionsPage } from '../missions/MissionsPage'
import { DispatchPage } from '../missions/DispatchPage'
import { OverviewPage } from '../dashboard/OverviewPage'
import { ReservedPage } from './ReservedPage'
import type { ReactNode } from 'react'

function ProtectedPage({ children, adminOnly = false }: { children: ReactNode; adminOnly?: boolean }) {
  const { user } = useAuth()
  if (!user || (user.role !== 'ADMIN' && user.role !== 'OPERADOR')) return <Navigate to="/login" replace />
  if (adminOnly && user.role !== 'ADMIN') return <Navigate to="/" replace />
  return children
}
export function App() {
  return <AuthProvider><BrowserRouter><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/" element={<ProtectedPage><OverviewPage /></ProtectedPage>} />
    <Route path="/fleet" element={<ProtectedPage><OperationsPage /></ProtectedPage>} />
    <Route path="/missions" element={<ProtectedPage><MissionsPage /></ProtectedPage>} />
    <Route path="/missions/new" element={<ProtectedPage><MissionFormPage /></ProtectedPage>} />
    <Route path="/missions/dispatch" element={<ProtectedPage><DispatchPage /></ProtectedPage>} />
    <Route path="/missions/:missionId" element={<ProtectedPage><MissionDetailsPage /></ProtectedPage>} />
    <Route path="/alerts" element={<ProtectedPage><ReservedPage kind="ALERTAS" /></ProtectedPage>} />
    <Route path="/users" element={<ProtectedPage adminOnly><ReservedPage kind="USUÁRIOS" /></ProtectedPage>} />
    <Route path="/profile" element={<ProtectedPage><ReservedPage kind="PERFIL" /></ProtectedPage>} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></BrowserRouter></AuthProvider>
}
