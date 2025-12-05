import { useState } from 'react';
import { Box, CssBaseline, ThemeProvider } from '@mui/material';
import theme from './theme';
import { styles } from './theme/styles';
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

const DEFAULT_GUARDRAILS: GuardrailFlags = {
  pii: true,
  financial: true,
  credentials: true,
  offtopic: true,
};

function App() {
  const [guardrails, setGuardrails] = useState<GuardrailFlags>(DEFAULT_GUARDRAILS);
  const [bypassCache, setBypassCache] = useState(false);

  // Custom hooks
  const { health, cacheStats, loading: healthLoading, refreshHealth, refreshCacheStats, clearCache } = useHealth();
  const { messages, loading: queryLoading, sessionId, sendQuery, newSession } = useQuery();

  const handleToggleGuardrail = (key: keyof GuardrailFlags) => {
    setGuardrails((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleRefresh = async () => {
    await Promise.all([refreshHealth(), refreshCacheStats()]);
  };

  const handleSendQuery = async (query: string, file?: File) => {
    await sendQuery(query, guardrails, bypassCache, file);
  };

  const handleNewSession = () => {
    newSession();
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={styles.layout.root}>
        {/* Sidebar */}
        <Box sx={styles.layout.sidebar}>
          <AWSToolingPanel health={health} loading={healthLoading} />
          <GuardrailsPanel guardrails={guardrails} onToggle={handleToggleGuardrail} />
        </Box>

        {/* Main Content */}
        <Box sx={styles.layout.mainContent}>
          <Header
            health={health}
            cacheStats={cacheStats}
            sessionId={sessionId}
            onRefresh={handleRefresh}
            onClearCache={clearCache}
            onNewSession={handleNewSession}
            loading={healthLoading}
          />

          {/* Chat Area */}
          <ChatPanel messages={messages} loading={queryLoading} />

          {/* Query Input */}
          <QueryInput
            onSend={handleSendQuery}
            onClear={newSession}
            loading={queryLoading}
            bypassCache={bypassCache}
            onBypassCacheChange={setBypassCache}
            messages={messages}
          />
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;
