/**
 * ProjectFolder - Drop target for chat sessions.
 *
 * Features:
 * - Collapsible folder structure
 * - Drop target for chat session drag and drop
 * - Visual feedback on hover/drop
 */

import { useState, useCallback, ReactNode } from 'react';
import { useDrop } from 'react-dnd';
import { FolderOpen, FolderClosed, ChevronRight, MoreHorizontal, Pencil, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { DRAG_TYPE_CHAT_SESSION, type ChatSessionDragItem } from './chat-list-item';
import type { ChatProjectResponse } from '@/api/chat';

export interface ProjectFolderProps {
  /** Project data */
  project: ChatProjectResponse;
  /** Number of sessions in this project */
  sessionCount: number;
  /** Whether the folder is open */
  isOpen?: boolean;
  /** Callback when folder open state changes */
  onOpenChange?: (open: boolean) => void;
  /** Callback when a session is dropped into this project */
  onDrop: (sessionId: string) => void;
  /** Callback to rename the project (optional) */
  onRename?: (newName: string) => void;
  /** Callback to delete the project (optional) */
  onDelete?: () => void;
  /** Children (chat session items) */
  children: ReactNode;
}

export function ProjectFolder({
  project,
  sessionCount,
  isOpen: controlledIsOpen,
  onOpenChange,
  onDrop,
  onRename,
  onDelete,
  children,
}: ProjectFolderProps) {
  const [internalIsOpen, setInternalIsOpen] = useState(true);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(project.name);

  // Use controlled or internal state
  const isOpen = controlledIsOpen ?? internalIsOpen;
  const handleOpenChange = onOpenChange ?? setInternalIsOpen;

  // Set up drop target
  const [{ isOver, canDrop }, drop] = useDrop<ChatSessionDragItem, void, { isOver: boolean; canDrop: boolean }>({
    accept: DRAG_TYPE_CHAT_SESSION,
    drop: (item) => {
      // Only drop if session isn't already in this project
      if (item.projectId !== project.projectId) {
        onDrop(item.sessionId);
      }
    },
    canDrop: (item) => item.projectId !== project.projectId,
    collect: (monitor) => ({
      isOver: monitor.isOver(),
      canDrop: monitor.canDrop(),
    }),
  });

  const handleStartRename = useCallback(() => {
    setRenameValue(project.name);
    setIsRenaming(true);
  }, [project.name]);

  const handleSaveRename = useCallback(() => {
    const trimmed = renameValue.trim();
    setIsRenaming(false);
    if (trimmed && trimmed !== project.name && onRename) {
      onRename(trimmed);
    } else {
      setRenameValue(project.name);
    }
  }, [renameValue, project.name, onRename]);

  const handleCancelRename = useCallback(() => {
    setIsRenaming(false);
    setRenameValue(project.name);
  }, [project.name]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSaveRename();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        handleCancelRename();
      }
    },
    [handleSaveRename, handleCancelRename]
  );

  return (
    <div
      ref={drop as unknown as React.LegacyRef<HTMLDivElement>}
      className={cn(
        'rounded-md transition-colors',
        isOver && canDrop && 'bg-primary/10 ring-2 ring-primary/50'
      )}
    >
      <Collapsible open={isOpen} onOpenChange={handleOpenChange}>
        <div className="group flex items-center gap-1 px-2 py-1.5 rounded-md hover:bg-muted/50 transition-colors">
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className="flex items-center gap-2 flex-1 min-w-0 text-left text-xs"
            >
              <ChevronRight
                className={cn(
                  'h-3 w-3 shrink-0 transition-transform',
                  isOpen && 'rotate-90'
                )}
              />
              {isOpen ? (
                <FolderOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              ) : (
                <FolderClosed className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              )}

              {isRenaming ? (
                <input
                  type="text"
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={handleSaveRename}
                  onKeyDown={handleKeyDown}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 bg-transparent border-b border-primary outline-none text-xs min-w-0"
                  maxLength={50}
                  autoFocus
                />
              ) : (
                <span className="truncate flex-1 font-medium">{project.name}</span>
              )}
            </button>
          </CollapsibleTrigger>

          <Badge variant="secondary" className="h-4 px-1.5 text-[10px] shrink-0">
            {sessionCount}
          </Badge>

          {/* Project menu - only show if handlers are provided */}
          {(onRename || onDelete) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    'h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity ml-1',
                    'focus:opacity-100'
                  )}
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal className="h-3 w-3" />
                  <span className="sr-only">Project options</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                {onRename && (
                  <DropdownMenuItem onClick={handleStartRename}>
                    <Pencil className="h-4 w-4 mr-2" />
                    Rename
                  </DropdownMenuItem>
                )}
                {onRename && onDelete && <DropdownMenuSeparator />}
                {onDelete && (
                  <DropdownMenuItem
                    onClick={onDelete}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>

        <CollapsibleContent>
          <div className="pl-6 space-y-0.5">{children}</div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

/**
 * UnorganizedDropTarget - Drop target for removing sessions from projects.
 *
 * When a session is dropped here, it's removed from its project.
 */
export interface UnorganizedDropTargetProps {
  /** Callback when a session is dropped */
  onDrop: (sessionId: string) => void;
  /** Children to render */
  children: ReactNode;
}

export function UnorganizedDropTarget({ onDrop, children }: UnorganizedDropTargetProps) {
  const [{ isOver, canDrop }, drop] = useDrop<ChatSessionDragItem, void, { isOver: boolean; canDrop: boolean }>({
    accept: DRAG_TYPE_CHAT_SESSION,
    drop: (item) => {
      if (item.projectId) {
        onDrop(item.sessionId);
      }
    },
    canDrop: (item) => item.projectId !== null,
    collect: (monitor) => ({
      isOver: monitor.isOver(),
      canDrop: monitor.canDrop(),
    }),
  });

  return (
    <div
      ref={drop as unknown as React.LegacyRef<HTMLDivElement>}
      className={cn(
        'rounded-md transition-colors',
        isOver && canDrop && 'bg-primary/10 ring-2 ring-primary/50'
      )}
    >
      {children}
    </div>
  );
}
