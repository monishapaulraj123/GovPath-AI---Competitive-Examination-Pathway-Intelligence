import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  CalendarClock,
  ClipboardCheck,
  Compass,
  FileCheck2,
  GitBranch,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Route,
  Scale,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  UserCircle,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface NavSection {
  title: string;
  items: { label: string; to: string; icon: React.ReactNode }[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: 'OVERVIEW',
    items: [
      { label: 'Dashboard', to: '/', icon: <LayoutDashboard className="w-4 h-4" /> },
      { label: 'AI Counsellor', to: '/counsellor', icon: <Bot className="w-4 h-4" /> },
    ],
  },
  {
    title: 'EXAM INTELLIGENCE',
    items: [
      { label: 'Exam Explorer', to: '/exams', icon: <Compass className="w-4 h-4" /> },
      { label: 'Exam Comparison', to: '/compare', icon: <Scale className="w-4 h-4" /> },
      { label: 'Competency Knowledge Graph', to: '/knowledge-graph', icon: <Network className="w-4 h-4" /> },
    ],
  },
  {
    title: 'MY PREPARATION',
    items: [
      { label: 'Readiness Profile', to: '/readiness', icon: <ShieldCheck className="w-4 h-4" /> },
      { label: 'Assessments', to: '/assessments', icon: <ClipboardCheck className="w-4 h-4" /> },
      { label: 'Gap Analysis', to: '/gap-analysis', icon: <Target className="w-4 h-4" /> },
      { label: 'Knowledge Transfer', to: '/knowledge-transfer', icon: <ArrowLeftRight className="w-4 h-4" /> },
      { label: 'Retention Tracker', to: '/retention', icon: <History className="w-4 h-4" /> },
    ],
  },
  {
    title: 'AI PLANNING',
    items: [
      { label: 'AI Pathway Planner', to: '/pathway-planner', icon: <Route className="w-4 h-4" /> },
      { label: 'Adaptive Study Plan', to: '/study-plan', icon: <CalendarClock className="w-4 h-4" /> },
      { label: 'What-if Simulator', to: '/simulator', icon: <SlidersHorizontal className="w-4 h-4" /> },
    ],
  },
  {
    title: 'PERFORMANCE',
    items: [
      { label: 'Performance Analytics', to: '/analytics', icon: <BarChart3 className="w-4 h-4" /> },
      { label: 'Mock Tests', to: '/mock-tests', icon: <FileCheck2 className="w-4 h-4" /> },
      { label: 'Practice & Revision', to: '/practice', icon: <BookOpen className="w-4 h-4" /> },
      { label: 'Error Analysis', to: '/error-analysis', icon: <AlertTriangle className="w-4 h-4" /> },
    ],
  },
  {
    title: 'SYSTEM',
    items: [
      { label: 'Notifications', to: '/notifications', icon: <Bell className="w-4 h-4" /> },
      { label: 'My Profile', to: '/profile', icon: <UserCircle className="w-4 h-4" /> },
      { label: 'Settings', to: '/settings', icon: <Settings className="w-4 h-4" /> },
    ],
  },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const SidebarContent = () => (
    <div className="gov-sidebar flex flex-col h-full select-none">
      {/* Brand */}
      <div className="px-5 py-4 border-b gov-sidebar-divider flex items-center justify-between">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
          <div className="w-9 h-9 rounded-lg bg-white flex items-center justify-center shadow-sm">
            <GitBranch className="w-5 h-5 text-gp-primary" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-white">GovPath AI</div>
            <div className="text-[11px] font-medium text-[#F2EBF6]">Government Exam Intelligence</div>
          </div>
        </div>
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden text-[#F2EBF6] hover:text-white p-1 rounded-lg hover:bg-[#704387]"
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation Sections */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {NAV_SECTIONS.map((sec) => (
          <div key={sec.title}>
            <div className="gov-sidebar-section px-3 mb-1.5 text-[10px] font-semibold tracking-widest">
              {sec.title}
            </div>
            <div className="space-y-0.5">
              {sec.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    isActive ? 'gov-sidebar-link-active' : 'gov-sidebar-link'
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span className={isActive ? 'text-gp-primary' : 'text-[#F2EBF6]'}>{item.icon}</span>
                      <span className="truncate">{item.label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom User Card */}
      <div className="gov-sidebar-footer p-3">
        <div className="flex items-center justify-between gap-2 px-2 py-1.5">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-white truncate">{user?.display_name || user?.full_name}</p>
            <p className="text-[11px] text-[#EAE3F0] truncate">
              {user?.is_demo ? 'Demo Workspace' : user?.email}
            </p>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="p-1.5 rounded-lg text-[#F2EBF6] hover:text-white hover:bg-[#613774] transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-gp-bg">
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 sticky top-0 h-screen">
        <SidebarContent />
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div className="fixed inset-0 bg-[#292633]/40" onClick={() => setMobileOpen(false)} />
          <div className="relative w-72 max-w-[85vw] h-full z-10">
            <SidebarContent />
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Utility Header */}
        <header className="sticky top-0 z-30 h-14 bg-gp-surface border-b border-gp-border px-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 rounded-lg text-gp-ink-secondary hover:bg-gp-bg hover:text-gp-primary"
              aria-label="Open navigation"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="hidden sm:flex items-center gap-2 text-xs text-gp-ink-secondary">
              <Activity className="w-3.5 h-3.5 text-gp-primary" />
              <span>Primary Target:</span>
              <span className="px-2.5 py-0.5 rounded-md bg-gp-primary-light text-gp-primary font-semibold border border-gp-primary-border">
                {user?.primary_target_exam?.replace('_', ' ') || 'UPSC CSE'}
              </span>
              {user?.is_demo && (
                <span className="px-2 py-0.5 rounded-md bg-gp-warning-bg text-gp-warning font-medium border border-[#B45309]/20">
                  Demo Mode
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {location.pathname !== '/assessments' && (
              <button
                onClick={() => navigate('/assessments')}
                className="hidden sm:inline-flex gov-btn-secondary px-3 py-1.5 text-xs"
              >
                <ClipboardCheck className="w-3.5 h-3.5 text-gp-primary" />
                Diagnostic Test
              </button>
            )}
            {location.pathname !== '/counsellor' && (
              <button
                onClick={() => navigate('/counsellor')}
                className="gov-btn-primary px-3 py-1.5 text-xs"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Ask AI Counsellor
              </button>
            )}
            <button
              onClick={() => navigate('/notifications')}
              className="p-2 rounded-lg text-gp-ink-secondary hover:bg-gp-primary-light hover:text-gp-primary transition-colors"
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1440px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
