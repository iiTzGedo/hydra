import { useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Eye, EyeOff, KeyRound, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { useResetPassword } from '@/api/auth';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { fadeInVariants, scaleVariants } from '@/lib/animations';

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const resetPasswordMutation = useResetPassword();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!token) {
      setError('Invalid or missing reset token');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    try {
      await resetPasswordMutation.mutateAsync({ token, newPassword: password });
      setSuccess(true);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to reset password. The link may have expired.');
    }
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted p-4">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeInVariants}
          className="w-full max-w-md"
        >
          <motion.div
            variants={scaleVariants}
            className="rounded-xl border bg-card p-8 shadow-lg text-center"
          >
            <AlertCircle className="mx-auto h-16 w-16 text-error" />
            <h2 className="mt-4 text-xl font-semibold">Invalid Reset Link</h2>
            <p className="mt-2 text-muted-foreground">
              This password reset link is invalid or has expired. Please request a new one.
            </p>
            <Link
              to={ROUTES.FORGOT_PASSWORD}
              className={cn(
                'mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors'
              )}
            >
              Request New Link
            </Link>
          </motion.div>
        </motion.div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted p-4">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeInVariants}
          className="w-full max-w-md"
        >
          <motion.div
            variants={scaleVariants}
            className="rounded-xl border bg-card p-8 shadow-lg text-center"
          >
            <CheckCircle className="mx-auto h-16 w-16 text-success" />
            <h2 className="mt-4 text-xl font-semibold">Password Reset Successful</h2>
            <p className="mt-2 text-muted-foreground">
              Your password has been reset successfully. You can now sign in with your new password.
            </p>
            <button
              onClick={() => navigate(ROUTES.LOGIN)}
              className={cn(
                'mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors'
              )}
            >
              Go to Sign In
            </button>
          </motion.div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <motion.div
        initial="hidden"
        animate="visible"
        variants={fadeInVariants}
        className="w-full max-w-md"
      >
        <motion.div
          variants={scaleVariants}
          className="mb-8 text-center"
        >
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-hydra-blue text-white text-2xl font-bold shadow-lg">
            H
          </div>
          <h1 className="mt-4 text-3xl font-bold">Hydra</h1>
          <p className="mt-2 text-muted-foreground">Infrastructure Intelligence Platform</p>
        </motion.div>

        <motion.div
          variants={fadeInVariants}
          className="rounded-xl border bg-card p-6 shadow-lg"
        >
          <h2 className="mb-2 text-xl font-semibold">Reset your password</h2>
          <p className="mb-6 text-sm text-muted-foreground">
            Enter your new password below.
          </p>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-4 rounded-lg bg-error/10 p-3 text-sm text-error"
            >
              {error}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1.5">
                New Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter new password"
                  required
                  autoComplete="new-password"
                  className={cn(
                    'w-full rounded-lg border bg-background px-3 py-2 pr-10 text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring',
                    'placeholder:text-muted-foreground'
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Must be at least 8 characters</p>
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium mb-1.5">
                Confirm New Password
              </label>
              <div className="relative">
                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm new password"
                  required
                  autoComplete="new-password"
                  className={cn(
                    'w-full rounded-lg border bg-background px-3 py-2 pr-10 text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring',
                    'placeholder:text-muted-foreground'
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={resetPasswordMutation.isPending}
              className={cn(
                'flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {resetPasswordMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <KeyRound className="h-4 w-4" />
              )}
              Reset Password
            </button>
          </form>
        </motion.div>
      </motion.div>
    </div>
  );
}
