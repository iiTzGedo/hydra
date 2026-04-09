import { FileText } from 'lucide-react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { Card, CardContent } from '@/components/ui/card';

export default function DocsPage() {
  useDocumentTitle('Documentation');

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title="Documentation"
        subtitle="Living documentation, auto-generated and hybrid-authored infrastructure guides"
        showBackButton={false}
      />

      <Card>
        <CardContent className="p-8 text-center">
          <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Documentation system</h3>
          <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
            The documentation system is being built. Documents are auto-generated from
            infrastructure profiles, discovery results, and topology data. Manage documents
            via the API while the web interface is under development.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
