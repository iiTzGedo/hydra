import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Eye, EyeOff, LogIn, Loader2 } from 'lucide-react';
import { useLogin } from '@/api/auth';
import { useAuthStore } from '@/stores/auth-store';
import { getErrorMessage } from '@/lib/api-client';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { fadeInVariants, scaleVariants } from '@/lib/animations';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login: setAuth } = useAuthStore();
  const loginMutation = useLogin();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || ROUTES.DASHBOARD;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      const response = await loginMutation.mutateAsync({ username, password });
      setAuth(response.user, response.accessToken, response.refreshToken);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Invalid username or password'));
    }
  };

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
          <h2 className="mb-6 text-xl font-semibold">Sign in to your account</h2>

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
              <label htmlFor="username" className="block text-sm font-medium mb-1.5">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
                autoComplete="username"
                className={cn(
                  'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                  'focus:outline-none focus:ring-2 focus:ring-ring',
                  'placeholder:text-muted-foreground'
                )}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
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
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="rounded border-gray-300" />
                Remember me
              </label>
              <Link
                to={ROUTES.FORGOT_PASSWORD}
                className="text-sm text-primary hover:underline"
              >
                Forgot password?
              </Link>
            </div>

            <button
              type="submit"
              disabled={loginMutation.isPending}
              className={cn(
                'flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {loginMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogIn className="h-4 w-4" />
              )}
              Sign in
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            Don't have an account?{' '}
            <Link to={ROUTES.REGISTER} className="text-primary hover:underline">
              Sign up
            </Link>
          </div>
        </motion.div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} Hydra. AI-powered infrastructure management.
        </p>
      </motion.div>
    </div>
  );
}
