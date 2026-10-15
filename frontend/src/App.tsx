import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import NewInterview from './pages/NewInterview'
import MatchAnalysis from './pages/MatchAnalysis'
import InterviewRoom from './pages/InterviewRoom'
import Results from './pages/Results'
import Layout from './components/Layout'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewInterview />} />
          <Route path="/match/:matchId" element={<MatchAnalysis />} />
          <Route path="/results/:sessionId" element={<Results />} />
        </Route>
        {/* Interview room has its own full-screen layout */}
        <Route path="/interview/:sessionId" element={<InterviewRoom />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
