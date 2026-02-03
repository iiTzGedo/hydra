import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Eye, EyeOff, UserPlus, Loader2, CheckCircle } from 'lucide-react';
import { useRegister, useRegisterWithToken } from '@/api/auth';
import { getErrorMessage } from '@/lib/api-client';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { fadeInVariants, scaleVariants } from '@/lib/animations';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const registerMutation = useRegister();
  const registerWithTokenMutation = useRegisterWithToken();

  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    try {
      if (token) {
        await registerWithTokenMutation.mutateAsync({
          registrationToken: token,
          username: formData.username,
          email: formData.email,
          password: formData.password,
        });
      } else {
        await registerMutation.mutateAsync({
          username: formData.username,
          email: formData.email,
          password: formData.password,
        });
      }
      setSuccess(true);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Registration failed. Please try again.'));
    }
  };

  const isPending = registerMutation.isPending || registerWithTokenMutation.isPending;

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
            <h2 className="mt-4 text-xl font-semibold">Registration Successful!</h2>
            <p className="mt-2 text-muted-foreground">
              {token
                ? 'Your account has been created. You can now sign in.'
                : 'Your account has been created and is pending approval. You will be notified once an administrator approves your account.'}
            </p>
            <Link
              to={ROUTES.LOGIN}
              className={cn(
                'mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors'
              )}
            >
              Go to Sign In
            </Link>
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
          <h2 className="mb-6 text-xl font-semibold">Create your account</h2>

          {token && (
            <div className="mb-4 rounded-lg bg-primary/10 p-3 text-sm text-primary">
              You're registering with an invitation token.
            </div>
          )}

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
                name="username"
                type="text"
                value={formData.username}
                onChange={handleChange}
                placeholder="Choose a username"
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
              <label htmlFor="email" className="block text-sm font-medium mb-1.5">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="Enter your email"
                required
                autoComplete="email"
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
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Create a password"
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
                Confirm Password
              </label>
              <div className="relative">
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  placeholder="Confirm your password"
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
              disabled={isPending}
              className={cn(
                'flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <UserPlus className="h-4 w-4" />
              )}
              Create Account
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to={ROUTES.LOGIN} className="text-primary hover:underline">
              Sign in
            </Link>
          </div>
        </motion.div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          By creating an account, you agree to our Terms of Service and Privacy Policy.
        </p>
      </motion.div>
    </div>
  );
}
