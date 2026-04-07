import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'sonner';
import { useMe } from '@/api/auth';
import { AppRouter } from '@/router';
import { ThemeProvider } from '@/components/theme-provider';
import { ErrorBoundary } from '@/components/error-boundary';

function AuthBootstrap() {
  useMe();

  return null;
}

function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <BrowserRouter>
        <AuthBootstrap />
        <ErrorBoundary>
          <AppRouter />
        </ErrorBoundary>
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
