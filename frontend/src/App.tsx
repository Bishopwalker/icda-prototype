import { useState, useCallback, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Box, CssBaseline, ThemeProvider, CircularProgress } from '@mui/material';
import { alpha } from '@mui/material/styles';
import theme, { colors } from './theme';
import type { GuardrailFlags } from './types';

// Components
import { Header } from './components/Header';
import { AWSToolingPanel } from './components/AWSToolingPanel';
import { GuardrailsPanel } from './components/GuardrailsPanel';
import { ChatPanel } from './components/chat';
import { QueryInput } from './components/QueryInput';

// Hooks
import { useHealth } from './hooks/useHealth';
import { useQuery } from './hooks/useQuery';

// Lazy load admin components
const AdminLayout = lazy(() => import('./components/admin/AdminLayout'));
const IndexDashboard = lazy(() => import('./components/admin/dashboard/IndexDashboard'));
const ChunkBrowser = lazy(() => import('./components/admin/chunks/ChunkBrowser'));
const SearchPlayground = lazy(() => import('./components/admin/playground/SearchPlayground'));

const DEFAULT_GUARDRAILS: GuardrailFlags = {
  pii: true,
  financial: true,
  credentials: true,
  offtopic: true,
};

function LoadingFallback() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <CircularProgress />
    </Box>
  );
}

function MainChat() {
  const [guardrails, setGuardrails] = useState<GuardrailFlags>(DEFAULT_GUARDRAILS);
  const [bypassCache, setBypassCache] = useState(false);
  const [pendingQuery, setPendingQuery] = useState<string | undefined>(undefined);

  // Custom hooks
  const { health, cacheStats, loading: healthLoading, refreshHealth, refreshCacheStats, clearCache } = useHealth();
  const { messages, loading: queryLoading, sessionId, sendQuery, newSession } = useQuery();

  const handleToggleGuardrail = (key: keyof GuardrailFlags) => {
    setGuardrails((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleDisableAllGuardrails = () => {
    setGuardrails({ pii: false, financial: false, credentials: false, offtopic: false });
  };

  const handleEnableAllGuardrails = () => {
    setGuardrails({ pii: true, financial: true, credentials: true, offtopic: true });
  };

  const handleRefresh = async () => {
    await Promise.all([refreshHealth(), refreshCacheStats()]);
  };

  const handleSendQuery = async (query: string, file?: File) => {
    setPendingQuery(undefined);
    await sendQuery(query, guardrails, bypassCache, file);
  };

  const handleNewSession = () => {
    setPendingQuery(undefined);
    newSession();
  };

  const handleQuickAction = useCallback((query: string) => {
    setPendingQuery(query);
  }, []);

  return (
    <Box
      component="main"
      sx={{
        display: 'flex',
        height: '100vh',
        maxHeight: '100vh',
        overflow: 'hidden',
        backgroundColor: 'background.default',
        background: `linear-gradient(135deg, ${colors.background.default} 0%, ${colors.background.paper} 50%, ${colors.background.default} 100%)`,
      }}
    >
      {/* Sidebar */}
      <Box
        component="aside"
        role="complementary"
        aria-label="Tooling and Guardrails Panel"
        sx={{
          width: 280,
          flexShrink: 0,
          borderRight: `1px solid ${alpha(colors.primary.main, 0.2)}`,
          backgroundColor: alpha(colors.background.paper, 0.8),
          backdropFilter: 'blur(10px)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <AWSToolingPanel health={health} loading={healthLoading} />
        <GuardrailsPanel
          guardrails={guardrails}
          onToggle={handleToggleGuardrail}
          onDisableAll={handleDisableAllGuardrails}
          onEnableAll={handleEnableAllGuardrails}
        />
      </Box>

      {/* Main Content */}
      <Box
        component="section"
        role="main"
        aria-label="Main Chat Content"
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        <Header
          health={health}
          cacheStats={cacheStats}
          sessionId={sessionId}
          onRefresh={handleRefresh}
          onClearCache={clearCache}
          onNewSession={handleNewSession}
          loading={healthLoading}
        />

        {/* Chat Area with Welcome Panel and Quick Actions */}
        <ChatPanel
          messages={messages}
          loading={queryLoading}
          onQuickAction={handleQuickAction}
        />

        {/* Query Input with address suggestions */}
        <QueryInput
          onSend={handleSendQuery}
          onClear={handleNewSession}
          loading={queryLoading}
          bypassCache={bypassCache}
          onBypassCacheChange={setBypassCache}
          messages={messages}
          initialQuery={pendingQuery}
        />
      </Box>
    </Box>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            {/* Main Chat App */}
            <Route path="/" element={<MainChat />} />

            {/* Admin Routes */}
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="dashboard" element={<IndexDashboard />} />
              <Route path="chunks" element={<ChunkBrowser />} />
              <Route path="playground" element={<SearchPlayground />} />
            </Route>

            {/* Catch all - redirect to home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;