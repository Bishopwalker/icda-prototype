import { createTheme, alpha } from '@mui/material/styles';

// USPS-Inspired Color Palette with high contrast
export const colors = {
  primary: {
    main: '#004B87',     // USPS Blue
    light: '#0077C8',    // Brighter blue for accents
    dark: '#003366',     // Darker blue
    contrastText: '#fff',
  },
  secondary: {
    main: '#DA291C',     // USPS Red
    light: '#FF5252',    // Brighter red
    dark: '#B71C1C',     // Darker red
    contrastText: '#fff',
  },
  accent: {
    main: '#00BFA5',     // Teal for AI responses
    light: '#64FFDA',    // Light teal
    dark: '#00897B',     // Dark teal
  },
  success: {
    main: '#2E7D32',
    light: '#4CAF50',
    dark: '#1B5E20',
  },
  error: {
    main: '#D32F2F',
    light: '#EF5350',
    dark: '#C62828',
  },
  warning: {
    main: '#ED6C02',
    light: '#FF9800',
    dark: '#E65100',
  },
  info: {
    main: '#0288D1',
    light: '#03A9F4',
    dark: '#01579B',
  },
  background: {
    default: '#0D1B2A',    // Deep navy
    paper: '#1B2838',      // Slightly lighter navy
    elevated: '#243447',   // Card/panel backgrounds
    chat: '#0F2027',       // Chat area background
  },
  text: {
    primary: '#FFFFFF',
    secondary: 'rgba(255, 255, 255, 0.75)',
    disabled: 'rgba(255, 255, 255, 0.5)',
    muted: 'rgba(255, 255, 255, 0.6)',
  },
  // USPS Brand Colors
  usps: {
    blue: '#004B87',
    red: '#DA291C',
    navy: '#1E3A5F',
    lightBlue: '#A1C4E9',
  },
  // AWS-themed indicators
  aws: {
    orange: '#FF9900',
    blue: '#232F3E',
  },
  // Guardrail colors (high contrast)
  guardrails: {
    pii: '#FF5252',
    financial: '#FFB300',
    credentials: '#AB47BC',
    offtopic: '#78909C',
  },
  // Route indicators
  routes: {
    cache: '#4CAF50',
    database: '#2196F3',
    nova: '#9C27B0',
  },
  // Quick action colors
  quickActions: {
    lookup: '#00BFA5',
    search: '#0077C8',
    stats: '#7C4DFF',
    address: '#FF6D00',
    list: '#00E676',
    help: '#FF4081',
  },
  neutral: {
    main: '#607D8B',
    light: '#90A4AE',
    dark: '#455A64',
  },
};

// Centralized spacing
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

// Centralized border radius
export const borderRadius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  xxl: 24,
  round: '50%',
};

// Centralized shadows
export const shadows = {
  sm: '0 1px 3px rgba(0,0,0,0.20), 0 1px 2px rgba(0,0,0,0.28)',
  md: '0 4px 8px rgba(0,0,0,0.25), 0 2px 4px rgba(0,0,0,0.20)',
  lg: '0 12px 24px rgba(0,0,0,0.25), 0 4px 8px rgba(0,0,0,0.15)',
  xl: '0 20px 40px rgba(0,0,0,0.30), 0 8px 16px rgba(0,0,0,0.15)',
  glow: (color: string) => `0 0 20px ${alpha(color, 0.4)}`,
};

// Centralized transitions
export const transitions = {
  fast: '0.15s ease-in-out',
  normal: '0.3s ease-in-out',
  slow: '0.5s ease-in-out',
  bounce: '0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
};

// Pane sizes for expandable panels
export const paneSizes = {
  response: {
    collapsed: 200,
    normal: 300,
    expanded: 600,
    maxExpanded: 900,
  },
  sidebar: {
    collapsed: 60,
    normal: 280,
  },
};

// Create the MUI theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: colors.primary,
    secondary: colors.secondary,
    success: colors.success,
    error: colors.error,
    warning: colors.warning,
    info: colors.info,
    background: colors.background,
    text: colors.text,
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '1.5rem',
      fontWeight: 600,
    },
    h4: {
      fontSize: '1.25rem',
      fontWeight: 600,
    },
    h5: {
      fontSize: '1rem',
      fontWeight: 600,
    },
    h6: {
      fontSize: '0.875rem',
      fontWeight: 600,
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
    caption: {
      fontSize: '0.75rem',
    },
  },
  shape: {
    borderRadius: borderRadius.md,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: `${colors.primary.main} ${colors.background.paper}`,
          '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
            width: 8,
            height: 8,
          },
          '&::-webkit-scrollbar-track, & *::-webkit-scrollbar-track': {
            background: colors.background.paper,
          },
          '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
            backgroundColor: colors.primary.main,
            borderRadius: 4,
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: borderRadius.md,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: borderRadius.lg,
          backgroundImage: 'none',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: borderRadius.sm,
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          '&.Mui-selected': {
            backgroundColor: alpha(colors.primary.main, 0.2),
          },
        },
      },
    },
  },
});

export default theme;