import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { LoadingState } from './components/UI';
import { AuthProvider, useAuth } from './context/AuthContext';
import AnalyticsPage from './pages/AnalyticsPage';
import AssessmentsPage from './pages/AssessmentsPage';
import CounsellorPage from './pages/CounsellorPage';
import DashboardPage from './pages/DashboardPage';
import ErrorAnalysisPage from './pages/ErrorAnalysisPage';
import ExamComparePage from './pages/ExamComparePage';
import ExamExplorerPage from './pages/ExamExplorerPage';
import GapAnalysisPage from './pages/GapAnalysisPage';
import KnowledgeGraphPage from './pages/KnowledgeGraphPage';
import KnowledgeTransferPage from './pages/KnowledgeTransferPage';
import LoginPage from './pages/LoginPage';
import NotificationsPage from './pages/NotificationsPage';
import PathwayPlannerPage from './pages/PathwayPlannerPage';
import PracticePage from './pages/PracticePage';
import ProfilePage from './pages/ProfilePage';
import ReadinessPage from './pages/ReadinessPage';
import RetentionPage from './pages/RetentionPage';
import SettingsPage from './pages/SettingsPage';
import SimulatorPage from './pages/SimulatorPage';
import StudyPlanPage from './pages/StudyPlanPage';

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gp-bg">
        <LoadingState label="Initializing GovPath AI Workspace..." />
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/counsellor" element={<CounsellorPage />} />
        <Route path="/exams" element={<ExamExplorerPage />} />
        <Route path="/exams/:examId" element={<ExamExplorerPage />} />
        <Route path="/compare" element={<ExamComparePage />} />
        <Route path="/knowledge-graph" element={<KnowledgeGraphPage />} />
        <Route path="/readiness" element={<ReadinessPage />} />
        <Route path="/assessments" element={<AssessmentsPage />} />
        <Route path="/gap-analysis" element={<GapAnalysisPage />} />
        <Route path="/knowledge-transfer" element={<KnowledgeTransferPage />} />
        <Route path="/retention" element={<RetentionPage />} />
        <Route path="/pathway-planner" element={<PathwayPlannerPage />} />
        <Route path="/study-plan" element={<StudyPlanPage />} />
        <Route path="/simulator" element={<SimulatorPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/mock-tests" element={<AssessmentsPage mockMode />} />
        <Route path="/practice" element={<PracticePage />} />
        <Route path="/error-analysis" element={<ErrorAnalysisPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
