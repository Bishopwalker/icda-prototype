import type { SxProps, Theme } from '@mui/material/styles';
import { alpha } from '@mui/material/styles';
import { colors, borderRadius, transitions, paneSizes } from './index';

// Centralized component styles
export const styles = {
  // Layout styles
  layout: {
    root: {
      display: 'flex',
      minHeight: '100vh',
      backgroundColor: 'background.default',
    } as SxProps<Theme>,

    mainContent: {
      flexGrow: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',  // Let children handle scroll
      minHeight: 0,        // Critical for flex scroll
    } as SxProps<Theme>,

    sidebar: {
      width: paneSizes.sidebar.normal,
      flexShrink: 0,
      borderRight: 1,
      borderColor: 'divider',
      backgroundColor: 'background.paper',
      transition: transitions.normal,
    } as SxProps<Theme>,
  },

  // Header styles
  header: {
    root: {
      py: 2,
      px: 3,
      borderBottom: 1,
      borderColor: 'divider',
      backgroundColor: 'background.paper',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    } as SxProps<Theme>,

    title: {
      fontWeight: 700,
      background: `linear-gradient(45deg, ${colors.primary.light}, ${colors.secondary.light})`,
      backgroundClip: 'text',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
    } as SxProps<Theme>,

    statusBadge: {
      display: 'flex',
      alignItems: 'center',
      gap: 1,
      px: 2,
      py: 0.5,
      borderRadius: borderRadius.lg,
      fontSize: '0.875rem',
    } as SxProps<Theme>,
  },

  // Panel styles
  panel: {
    root: {
      backgroundColor: 'background.paper',
      borderRadius: borderRadius.lg,
      border: 1,
      borderColor: 'divider',
      overflow: 'hidden',
    } as SxProps<Theme>,

    header: {
      px: 2,
      py: 1.5,
      borderBottom: 1,
      borderColor: 'divider',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      backgroundColor: 'background.elevated',
    } as SxProps<Theme>,

    content: {
      p: 2,
      overflowY: 'auto',
      transition: transitions.normal,
    } as SxProps<Theme>,

    expandable: {
      transition: `height ${transitions.normal}, max-height ${transitions.normal}`,
    } as SxProps<Theme>,
  },

  // Response pane specific styles
  responsePane: {
    collapsed: {
      height: paneSizes.response.collapsed,
      maxHeight: paneSizes.response.collapsed,
    } as SxProps<Theme>,

    normal: {
      height: paneSizes.response.normal,
      maxHeight: paneSizes.response.normal,
    } as SxProps<Theme>,

    expanded: {
      height: paneSizes.response.expanded,
      maxHeight: paneSizes.response.expanded,
    } as SxProps<Theme>,

    maxExpanded: {
      height: paneSizes.response.maxExpanded,
      maxHeight: paneSizes.response.maxExpanded,
    } as SxProps<Theme>,
  },

  // Button styles
  buttons: {
    guardrail: {
      base: {
        borderRadius: borderRadius.md,
        px: 2,
        py: 1,
        transition: transitions.fast,
        textTransform: 'none',
        fontWeight: 500,
      } as SxProps<Theme>,

      active: (color: string) => ({
        backgroundColor: alpha(color, 0.2),
        borderColor: color,
        color: color,
        '&:hover': {
          backgroundColor: alpha(color, 0.3),
        },
      }),

      inactive: {
        backgroundColor: 'transparent',
        borderColor: 'rgba(255, 255, 255, 0.23)',
        color: 'text.secondary',
        '&:hover': {
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
        },
      } as SxProps<Theme>,
    },

    aws: {
      backgroundColor: colors.aws.orange,
      color: colors.aws.blue,
      '&:hover': {
        backgroundColor: alpha(colors.aws.orange, 0.8),
      },
      fontWeight: 600,
    } as SxProps<Theme>,
  },

  // Chat/Message styles
  chat: {
    container: {
      flexGrow: 1,
      overflowY: 'auto',
      p: 2,
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    } as SxProps<Theme>,

    message: {
      base: {
        maxWidth: '95%',
        p: 2,
        borderRadius: borderRadius.lg,
        minHeight: 'auto',
        overflowY: 'auto',
        transition: transitions.fast,
        '&:hover': {
          backgroundColor: 'background.elevated',
        },
      } as SxProps<Theme>,

      user: {
        alignSelf: 'flex-end',
        backgroundColor: colors.primary.main,
        color: 'white',
        borderBottomRightRadius: borderRadius.sm,
      } as SxProps<Theme>,

      bot: {
        alignSelf: 'flex-start',
        backgroundColor: 'background.elevated',
        borderBottomLeftRadius: borderRadius.sm,
      } as SxProps<Theme>,

      error: {
        alignSelf: 'flex-start',
        backgroundColor: alpha(colors.error.main, 0.1),
        borderColor: colors.error.main,
        border: 1,
      } as SxProps<Theme>,

      blocked: {
        alignSelf: 'flex-start',
        backgroundColor: alpha(colors.warning.main, 0.1),
        borderColor: colors.warning.main,
        border: 1,
      } as SxProps<Theme>,
    },

    metadata: {
      display: 'flex',
      alignItems: 'center',
      gap: 1,
      mt: 1,
      fontSize: '0.75rem',
      color: 'text.secondary',
    } as SxProps<Theme>,
  },

  // Input styles
  input: {
    container: {
      p: 2,
      borderTop: 1,
      borderColor: 'divider',
      backgroundColor: 'background.paper',
    } as SxProps<Theme>,

    field: {
      '& .MuiOutlinedInput-root': {
        borderRadius: borderRadius.lg,
        backgroundColor: 'background.elevated',
      },
    } as SxProps<Theme>,
  },

  // File upload styles
  upload: {
    dropzone: {
      border: 2,
      borderStyle: 'dashed',
      borderColor: 'divider',
      borderRadius: borderRadius.lg,
      p: 4,
      textAlign: 'center',
      cursor: 'pointer',
      transition: transitions.fast,
      '&:hover': {
        borderColor: 'primary.main',
        backgroundColor: alpha(colors.primary.main, 0.05),
      },
    } as SxProps<Theme>,

    dropzoneActive: {
      borderColor: 'primary.main',
      backgroundColor: alpha(colors.primary.main, 0.1),
    } as SxProps<Theme>,

    fileList: {
      mt: 2,
      maxHeight: 200,
      overflowY: 'auto',
    } as SxProps<Theme>,

    fileItem: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      p: 1,
      borderRadius: borderRadius.sm,
      backgroundColor: 'background.elevated',
      mb: 1,
    } as SxProps<Theme>,
  },

  // Route badge styles
  routeBadge: {
    cache: {
      backgroundColor: alpha(colors.routes.cache, 0.2),
      color: colors.routes.cache,
    } as SxProps<Theme>,

    database: {
      backgroundColor: alpha(colors.routes.database, 0.2),
      color: colors.routes.database,
    } as SxProps<Theme>,

    nova: {
      backgroundColor: alpha(colors.routes.nova, 0.2),
      color: colors.routes.nova,
    } as SxProps<Theme>,
  },

  // Card styles
  card: {
    root: {
      backgroundColor: 'background.paper',
      borderRadius: borderRadius.lg,
      border: 1,
      borderColor: 'divider',
    } as SxProps<Theme>,

    interactive: {
      cursor: 'pointer',
      transition: transitions.fast,
      '&:hover': {
        borderColor: 'primary.main',
        transform: 'translateY(-2px)',
        boxShadow: 4,
      },
    } as SxProps<Theme>,
  },

  // Status indicator styles
  status: {
    dot: {
      width: 8,
      height: 8,
      borderRadius: '50%',
      display: 'inline-block',
    } as SxProps<Theme>,

    online: {
      backgroundColor: colors.success.main,
    } as SxProps<Theme>,

    offline: {
      backgroundColor: colors.error.main,
    } as SxProps<Theme>,

    loading: {
      backgroundColor: colors.warning.main,
    } as SxProps<Theme>,
  },

  // Utility styles
  utils: {
    flexCenter: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    } as SxProps<Theme>,

    flexBetween: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    } as SxProps<Theme>,

    flexColumn: {
      display: 'flex',
      flexDirection: 'column',
    } as SxProps<Theme>,

    scrollY: {
      overflowY: 'auto',
      overflowX: 'hidden',
    } as SxProps<Theme>,

    noWrap: {
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
    } as SxProps<Theme>,
  },
};

export default styles;