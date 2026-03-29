interface CommandOutputProps {
  output?: string | null;
  error?: string | null;
}

export function CommandOutput({ output, error }: CommandOutputProps) {
  if (!output && !error) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        No output
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {output && (
        <pre className="bg-zinc-950 text-zinc-100 rounded-lg p-4 font-mono text-sm overflow-auto max-h-96 whitespace-pre-wrap break-words">
          {output}
        </pre>
      )}
      {error && (
        <pre className="bg-zinc-950 text-red-400 rounded-lg p-4 font-mono text-sm overflow-auto max-h-96 whitespace-pre-wrap break-words">
          {error}
        </pre>
      )}
    </div>
  );
}
