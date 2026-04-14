import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  BookOpen,
  Clock3,
  Edit3,
  FileSearch,
  History,
  RefreshCw,
  Search,
  Sparkles,
} from 'lucide-react';
import { useDoc, useDocs, useDocsSearch, useDocsTree } from '@/api/docs';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';

export default function DocsPage() {
  useDocumentTitle('Documentation');

  const router = useRouter();
  const pathname = usePathname() ?? '/';
  const treeQuery = useDocsTree();
  const docsQuery = useDocs({ limit: 50, offset: 0 });
  const [searchQuery, setSearchQuery] = useState('');

  const tree = treeQuery.data ?? [];
  const docIdFromPath = pathname.startsWith('/docs/')
    ? pathname.replace('/docs/', '').split('/')[0] || null
    : null;
  const activeDocId = docIdFromPath && docIdFromPath !== 'category' ? docIdFromPath : null;
  const activeDocQuery = useDoc(activeDocId);
  const searchResults = useDocsSearch(searchQuery);

  const activeDoc = activeDocQuery.data;
  const recentDocs = docsQuery.data?.items ?? [];

  const resultCards = searchQuery.trim().length > 0
    ? searchResults.data ?? []
    : recentDocs;

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title="Documentation"
        subtitle="Portal for generated and manually curated infrastructure knowledge."
        showBackButton={false}
        actions={
          <>
            <Button variant="outline" size="sm" disabled={!activeDoc}>
              <Edit3 className="mr-2 h-4 w-4" />
              Edit Section
            </Button>
            <Button variant="outline" size="sm" disabled={!activeDoc}>
              <History className="mr-2 h-4 w-4" />
              Versions
            </Button>
            <Button size="sm" disabled={!activeDoc}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Regenerate
            </Button>
          </>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[280px,minmax(0,1fr),280px]">
        <Card className="overflow-hidden">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Knowledge Map</CardTitle>
            <CardDescription>Server-driven portal navigation tree</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[calc(100vh-18rem)] px-4 pb-4">
              {treeQuery.isLoading ? (
                <div className="flex items-center gap-3 py-6 text-sm text-muted-foreground">
                  <LoadingSpinner />
                  Loading documentation tree...
                </div>
              ) : (
                <div className="space-y-4 pt-1">
                  {tree.map((category) => (
                    <div key={category.nodeId} className="space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                        {category.title}
                      </div>
                      <div className="space-y-1">
                        {category.children.map((doc) => (
                          <button
                            key={doc.nodeId}
                            type="button"
                            onClick={() => router.push(`/docs/${doc.docId}`)}
                            className={cn(
                              'flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm transition-colors',
                              activeDocId === doc.docId
                                ? 'bg-primary/10 text-foreground'
                                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                            )}
                          >
                            <BookOpen className="h-4 w-4 shrink-0" />
                            <span className="truncate">{doc.title}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardContent className="p-4">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search documentation, procedures, or generated notes..."
                  className="pl-9"
                />
              </div>
            </CardContent>
          </Card>

          {activeDoc ? (
            <Card className="overflow-hidden">
              <CardHeader className="border-b border-border/60 bg-muted/30">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{activeDoc.type}</Badge>
                  <Badge variant={activeDoc.status === 'published' ? 'success' : 'secondary'}>
                    {activeDoc.status}
                  </Badge>
                  {activeDoc.category ? <Badge variant="secondary">{activeDoc.category}</Badge> : null}
                </div>
                <CardTitle className="text-2xl">{activeDoc.title}</CardTitle>
                <CardDescription>{activeDoc.description ?? 'Generated and manual sections rendered together.'}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-8 p-6">
                {activeDoc.sections.length > 0 ? (
                  activeDoc.sections
                    .sort((left, right) => left.order - right.order)
                    .map((section) => (
                      <section key={section.sectionId} id={section.sectionId} className="space-y-3">
                        <div className="flex items-center gap-2">
                          <h2 className="text-lg font-semibold">{section.title}</h2>
                          <Badge variant={section.source === 'generated' ? 'info' : 'secondary'}>
                            {section.source}
                          </Badge>
                        </div>
                        <div className="rounded-2xl border border-border/60 bg-background p-4">
                          <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
                            {section.content}
                          </pre>
                        </div>
                      </section>
                    ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 p-6">
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
                      {activeDoc.content}
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  {searchQuery.trim().length > 0 ? 'Search Results' : 'Portal Index'}
                </CardTitle>
                <CardDescription>
                  {searchQuery.trim().length > 0
                    ? 'Search across generated and manually authored documentation.'
                    : 'Recent and discoverable documents in the portal.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {searchResults.isLoading && searchQuery.trim().length > 0 ? (
                  <div className="flex items-center gap-3 py-4 text-sm text-muted-foreground">
                    <LoadingSpinner />
                    Searching docs...
                  </div>
                ) : resultCards.length > 0 ? (
                  resultCards.map((entry) => (
                    <button
                      key={entry.docId}
                      type="button"
                      onClick={() => router.push(`/docs/${entry.docId}`)}
                      className="w-full rounded-2xl border border-border/60 p-4 text-left transition-colors hover:bg-muted/40"
                    >
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{entry.type}</Badge>
                        {entry.category ? <Badge variant="secondary">{entry.category}</Badge> : null}
                      </div>
                      <div className="font-medium text-foreground">{entry.title}</div>
                      {'excerpt' in entry && entry.excerpt ? (
                        <p className="mt-2 text-sm text-muted-foreground">{entry.excerpt}</p>
                      ) : null}
                      <div className="mt-3 text-xs text-muted-foreground">
                        Updated {new Date(entry.updatedAt).toLocaleString()}
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 p-6 text-sm text-muted-foreground">
                    No documents matched this query.
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Document Rail</CardTitle>
              <CardDescription>TOC, linked entities, and freshness metadata</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {activeDoc ? (
                <>
                  <div className="space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      Table of Contents
                    </div>
                    {activeDoc.sections.map((section) => (
                      <a
                        key={section.sectionId}
                        href={`#${section.sectionId}`}
                        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                      >
                        <FileSearch className="h-4 w-4" />
                        <span className="truncate">{section.title}</span>
                      </a>
                    ))}
                  </div>

                  <Separator />

                  <div className="space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      Entity Context
                    </div>
                    {activeDoc.linkedEntities?.length ? (
                      activeDoc.linkedEntities.map((entity) => (
                        <Badge key={`${entity.entityType}-${entity.entityId}`} variant="outline" className="mr-2">
                          {entity.entityType}:{entity.entityId}
                        </Badge>
                      ))
                    ) : (
                      <div className="text-sm text-muted-foreground">No linked entities.</div>
                    )}
                  </div>

                  <Separator />

                  <div className="space-y-3 text-sm">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Clock3 className="h-4 w-4" />
                      Updated {new Date(activeDoc.updatedAt).toLocaleString()}
                    </div>
                    {activeDoc.lastGeneratedAt ? (
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Sparkles className="h-4 w-4" />
                        Generated {new Date(activeDoc.lastGeneratedAt).toLocaleString()}
                      </div>
                    ) : null}
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <History className="h-4 w-4" />
                      Version {activeDoc.version}
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-sm text-muted-foreground">
                  Select a document to see its TOC, linked infrastructure, and freshness controls.
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Portal Shortcuts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Link
                href={ROUTES.DASHBOARDS}
                className="block rounded-lg border border-border/60 px-3 py-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Open dashboards
              </Link>
              <Link
                href={ROUTES.CHAT}
                className="block rounded-lg border border-border/60 px-3 py-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Ask Hydra Chat
              </Link>
              <Link
                href={ROUTES.TIME_MACHINE}
                className="block rounded-lg border border-border/60 px-3 py-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Inspect historical state
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
