import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft, Mail, Loader2, CheckCircle } from 'lucide-react';
import { useRequestPasswordReset } from '@/api/auth';
import { getErrorMessage } from '@/lib/api-client';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { fadeInVariants, scaleVariants } from '@/lib/animations';

export default function ForgotPasswordPage() {
  const requestResetMutation = useRequestPasswordReset();

  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      await requestResetMutation.mutateAsync({ email });
      setSuccess(true);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to send reset email. Please try again.'));
    }
  };

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
            <h2 className="mt-4 text-xl font-semibold">Check Your Email</h2>
            <p className="mt-2 text-muted-foreground">
              If an account exists with the email <span className="font-medium">{email}</span>,
              you will receive a password reset link shortly.
            </p>
            <Link
              href={ROUTES.LOGIN}
              className={cn(
                'mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors'
              )}
            >
              Back to Sign In
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
          <h2 className="mb-2 text-xl font-semibold">Forgot your password?</h2>
          <p className="mb-6 text-sm text-muted-foreground">
            Enter your email address and we'll send you a link to reset your password.
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
              <label htmlFor="email" className="block text-sm font-medium mb-1.5">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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

            <button
              type="submit"
              disabled={requestResetMutation.isPending}
              className={cn(
                'flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {requestResetMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Mail className="h-4 w-4" />
              )}
              Send Reset Link
            </button>
          </form>

          <div className="mt-6">
            <Link
              href={ROUTES.LOGIN}
              className="flex items-center justify-center gap-2 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Sign In
            </Link>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
