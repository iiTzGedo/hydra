import { motion } from 'framer-motion';
import { Sidebar } from './sidebar';
import { Header } from './header';
import { useUiStore } from '@/stores/ui-store';
import { cn } from '@/lib/utils';
import { pageVariants } from '@/lib/animations';

interface RootLayoutProps {
  children: React.ReactNode;
}

export function RootLayout({ children }: RootLayoutProps) {
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar />

      {/* Main content area */}
      <div
        className={cn(
          'flex flex-1 flex-col overflow-hidden transition-all duration-200',
          sidebarCollapsed ? 'md:pl-[72px]' : 'md:pl-60'
        )}
      >
        {/* Header */}
        <Header />

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <motion.div
            initial="initial"
            animate="enter"
            exit="exit"
            variants={pageVariants}
            className="h-full"
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}
