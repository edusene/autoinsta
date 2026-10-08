import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Loading } from './components/ui'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import { ContactsPage } from './pages/ContactsPage'
import { DashboardPage } from './pages/DashboardPage'
import { InstagramCallbackPage, InstagramPage } from './pages/InstagramPage'
import { LogsPage } from './pages/LogsPage'
import { PrivacyPage } from './pages/PrivacyPage'
import { DataDeletionPage, SettingsPage } from './pages/SettingsPage'
import { TermsPage } from './pages/TermsPage'
import { NewWorkflowPage, WorkflowsPage } from './pages/WorkflowsPage'

const WorkflowEditorPage = lazy(() => import('./workflow/WorkflowEditor').then((m) => ({ default: m.WorkflowEditorPage })))

function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Loading />
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/data-deletion" element={<DataDeletionPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/politica-de-privacidade" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/termos-de-uso" element={<TermsPage />} />
          {/* Editor ocupa a tela toda (sem sidebar) */}
          <Route path="/workflows/:id" element={<RequireAuth><Suspense fallback={<Loading />}><WorkflowEditorPage /></Suspense></RequireAuth>} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/workflows" element={<WorkflowsPage />} />
            <Route path="/workflows/new" element={<NewWorkflowPage />} />
            <Route path="/workflows/:id/logs" element={<LogsPage />} />
            <Route path="/instagram" element={<InstagramPage />} />
            <Route path="/instagram/callback" element={<InstagramCallbackPage />} />
            <Route path="/contacts" element={<ContactsPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
