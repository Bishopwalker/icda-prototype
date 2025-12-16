import React, { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, Box, Typography, IconButton,
  CircularProgress,
} from '@mui/material';
import { Close as CloseIcon, VerifiedUser as ValidatorIcon } from '@mui/icons-material';
import { alpha } from '@mui/material/styles';
import { colors, borderRadius } from '../theme';

interface ValidatorProps {
  open: boolean;
  onClose: () => void;
}

interface ValidationResult {
  valid: boolean;
  message: string;
}

export const Validator: React.FC<ValidatorProps> = ({ open, onClose }) => {
  const [address, setAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);

  const handleValidate = async () => {
    if (!address.trim()) return;
    setLoading(true);
    setResult(null);

    try {
      // TODO: Add actual validation API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      setResult({ valid: true, message: 'Address validated successfully' });
    } catch {
      setResult({ valid: false, message: 'Validation failed' });
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setAddress('');
    setResult(null);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: colors.background.paper,
          borderRadius: borderRadius.lg,
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ValidatorIcon sx={{ color: colors.success.main }} />
          <Typography variant="h6">Address Validator</Typography>
        </Box>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        <TextField
          fullWidth
          multiline
          rows={3}
          placeholder="Enter address to validate..."
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          sx={{ mt: 1 }}
        />

        {result && (
          <Box
            sx={{
              mt: 2,
              p: 2,
              borderRadius: borderRadius.md,
              backgroundColor: result.valid
                ? alpha(colors.success.main, 0.1)
                : alpha(colors.error.main, 0.1),
              border: `1px solid ${result.valid ? colors.success.main : colors.error.main}`,
            }}
          >
            <Typography
              sx={{ color: result.valid ? colors.success.light : colors.error.light }}
            >
              {result.message}
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={handleClose} color="inherit">
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleValidate}
          disabled={loading || !address.trim()}
          startIcon={loading ? <CircularProgress size={16} /> : <ValidatorIcon />}
          sx={{
            backgroundColor: colors.success.main,
            '&:hover': { backgroundColor: colors.success.dark },
          }}
        >
          Validate
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default Validator;
