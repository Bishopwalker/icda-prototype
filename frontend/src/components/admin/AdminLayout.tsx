/**
 * Admin Layout - Main layout wrapper for admin pages
 */

import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  AppBar,
  Typography,
  IconButton,
  Divider,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Storage as StorageIcon,
  Search as SearchIcon,
  Home as HomeIcon,
  ArrowBack as ArrowBackIcon,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';
import { colors } from '../../theme';

const DRAWER_WIDTH = 240;

const navItems = [
  { path: '/admin/dashboard', label: 'Dashboard', icon: <DashboardIcon /> },
  { path: '/admin/chunks', label: 'Chunk Browser', icon: <StorageIcon /> },
  { path: '/admin/playground', label: 'Search Playground', icon: <SearchIcon /> },
];

function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
          ml: `${DRAWER_WIDTH}px`,
          backgroundColor: alpha(colors.background.paper, 0.95),
          backdropFilter: 'blur(10px)',
          borderBottom: `1px solid ${alpha(colors.primary.main, 0.2)}`,
        }}
        elevation={0}
      >
        <Toolbar>
          <Typography variant="h6" noWrap sx={{ flexGrow: 1, color: colors.text.primary }}>
            ICDA Admin
          </Typography>
          <IconButton
            onClick={() => navigate('/')}
            sx={{ color: colors.text.secondary }}
            title="Back to Chat"
          >
            <HomeIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Sidebar */}
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
            backgroundColor: alpha(colors.background.paper, 0.95),
            borderRight: `1px solid ${alpha(colors.primary.main, 0.2)}`,
          },
        }}
      >
        <Toolbar sx={{ justifyContent: 'center' }}>
          <IconButton onClick={() => navigate('/')} sx={{ mr: 1 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" sx={{ color: colors.primary.main }}>
            Admin Panel
          </Typography>
        </Toolbar>
        <Divider sx={{ borderColor: alpha(colors.primary.main, 0.2) }} />
        <List>
          {navItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                onClick={() => navigate(item.path)}
                selected={location.pathname === item.path}
                sx={{
                  '&.Mui-selected': {
                    backgroundColor: alpha(colors.primary.main, 0.15),
                    borderRight: `3px solid ${colors.primary.main}`,
                    '&:hover': {
                      backgroundColor: alpha(colors.primary.main, 0.2),
                    },
                  },
                  '&:hover': {
                    backgroundColor: alpha(colors.primary.main, 0.1),
                  },
                }}
              >
                <ListItemIcon sx={{ color: location.pathname === item.path ? colors.primary.main : colors.text.secondary }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  sx={{ color: location.pathname === item.path ? colors.primary.main : colors.text.primary }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
          backgroundColor: colors.background.default,
          minHeight: '100vh',
          overflow: 'auto',
        }}
      >
        <Toolbar /> {/* Spacer for fixed AppBar */}
        <Outlet />
      </Box>
    </Box>
  );
}

export default AdminLayout;
