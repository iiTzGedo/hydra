import { useEffect } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'sonner';
import { useMe } from '@/api/auth';
import { AppRouter } from '@/router';
import { ThemeProvider } from '@/components/theme-provider';
import { useAuthStore } from '@/stores/auth-store';

function AuthBootstrap() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const setLoading = useAuthStore((state) => state.setLoading);

  useMe();

  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false);
    }
  }, [isAuthenticated, setLoading]);

  return null;
}

function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <BrowserRouter>
        <AuthBootstrap />
        <AppRouter />
        <Toaster
          position="top-right"
          toastOptions={{
            classNames: {
              toast: 'bg-background border-border',
              title: 'text-foreground',
              description: 'text-muted-foreground',
            },
          }}
        />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
