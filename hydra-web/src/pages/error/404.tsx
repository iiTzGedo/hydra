import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Home, ArrowLeft } from 'lucide-react';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { fadeInVariants, scaleVariants } from '@/lib/animations';

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <motion.div
        initial="hidden"
        animate="visible"
        variants={fadeInVariants}
        className="w-full max-w-md text-center"
      >
        <motion.div variants={scaleVariants}>
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-muted">
            <span className="text-5xl font-bold text-muted-foreground">404</span>
          </div>
        </motion.div>

        <motion.div variants={fadeInVariants} className="mt-8">
          <h1 className="text-2xl font-bold">Page Not Found</h1>
          <p className="mt-2 text-muted-foreground">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </motion.div>

        <motion.div
          variants={fadeInVariants}
          className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center"
        >
          <button
            onClick={() => window.history.back()}
            className={cn(
              'inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium',
              'hover:bg-muted transition-colors'
            )}
          >
            <ArrowLeft className="h-4 w-4" />
            Go Back
          </button>
          <Link
            to={ROUTES.DASHBOARD}
            className={cn(
              'inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Home className="h-4 w-4" />
            Go to Dashboard
          </Link>
        </motion.div>
      </motion.div>
    </div>
  );
}
