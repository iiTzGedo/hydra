/**
 * ChatListItem - Draggable chat session item with context menu.
 *
 * Features:
 * - Drag and drop to move between projects
 * - Double-click to rename inline
 * - Ellipsis menu with options (rename, move, duplicate, export, delete)
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useDrag } from 'react-dnd';
import { MessageSquare, MoreHorizontal, Pencil, FolderOpen, Copy, Download, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { ChatSessionResponse, ChatProjectResponse } from '@/api/chat';

export const DRAG_TYPE_CHAT_SESSION = 'CHAT_SESSION';

export interface ChatSessionDragItem {
  sessionId: string;
  projectId: string | null;
  title: string;
}

export interface ChatListItemProps {
  /** Chat session data */
  session: ChatSessionResponse;
  /** Whether this item is currently selected */
  isActive: boolean;
  /** Callback when item is clicked */
  onSelect: () => void;
  /** Callback when title is changed */
  onRename: (newTitle: string) => void;
  /** Callback when session is moved to a project */
  onMoveToProject: (projectId: string | null) => void;
  /** Callback when session is duplicated */
  onDuplicate: () => void;
  /** Callback when session is exported */
  onExport: () => void;
  /** Callback when session is deleted */
  onDelete: () => void;
  /** Available projects for move operation */
  projects: ChatProjectResponse[];
}

export function ChatListItem({
  session,
  isActive,
  onSelect,
  onRename,
  onMoveToProject,
  onDuplicate,
  onExport,
  onDelete,
  projects,
}: ChatListItemProps) {
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(session.title || 'Untitled');
  const inputRef = useRef<HTMLInputElement>(null);

  // Set up drag source
  const [{ isDragging }, drag] = useDrag<ChatSessionDragItem, unknown, { isDragging: boolean }>({
    type: DRAG_TYPE_CHAT_SESSION,
    item: {
      sessionId: session.sessionId,
      projectId: session.projectId,
      title: session.title || 'Untitled',
    },
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  });

  // Focus input when entering rename mode
  useEffect(() => {
    if (isRenaming && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isRenaming]);

  // Sync rename value with session title
  useEffect(() => {
    if (!isRenaming) {
      setRenameValue(session.title || 'Untitled');
    }
  }, [session.title, isRenaming]);

  const handleStartRename = useCallback(() => {
    setRenameValue(session.title || 'Untitled');
    setIsRenaming(true);
  }, [session.title]);

  const handleSaveRename = useCallback(() => {
    const trimmed = renameValue.trim();
    setIsRenaming(false);
    if (trimmed && trimmed !== session.title) {
      onRename(trimmed);
    } else {
      setRenameValue(session.title || 'Untitled');
    }
  }, [renameValue, session.title, onRename]);

  const handleCancelRename = useCallback(() => {
    setIsRenaming(false);
    setRenameValue(session.title || 'Untitled');
  }, [session.title]);

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

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      handleStartRename();
    },
    [handleStartRename]
  );

  return (
    <div
      ref={drag}
      className={cn(
        'group flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-colors relative',
        'hover:bg-muted text-muted-foreground hover:text-foreground',
        isActive && 'bg-muted text-foreground',
        isDragging && 'opacity-50 cursor-grabbing'
      )}
    >
      {/* Clickable area for selection */}
      <button
        onClick={onSelect}
        className="flex items-center gap-2 flex-1 min-w-0 text-left"
        type="button"
      >
        <MessageSquare className="h-3.5 w-3.5 shrink-0" />

        {isRenaming ? (
          <input
            ref={inputRef}
            type="text"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={handleSaveRename}
            onKeyDown={handleKeyDown}
            onClick={(e) => e.stopPropagation()}
            className="flex-1 bg-transparent border-b border-primary outline-none text-xs min-w-0"
            maxLength={100}
          />
        ) : (
          <span
            className="truncate flex-1"
            onDoubleClick={handleDoubleClick}
            title={session.title || 'Untitled'}
          >
            {session.title || 'Untitled'}
          </span>
        )}
      </button>

      {/* Ellipsis menu - appears on hover */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              'h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity ml-2',
              'focus:opacity-100'
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
            <span className="sr-only">More options</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem onClick={handleStartRename}>
            <Pencil className="h-4 w-4 mr-2" />
            Rename
          </DropdownMenuItem>

          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <FolderOpen className="h-4 w-4 mr-2" />
              Move to Project
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-48">
              <DropdownMenuItem
                onClick={() => onMoveToProject(null)}
                disabled={!session.projectId}
              >
                <FolderOpen className="h-4 w-4 mr-2 opacity-50" />
                No Project
              </DropdownMenuItem>
              {projects.length > 0 && <DropdownMenuSeparator />}
              {projects.map((project) => (
                <DropdownMenuItem
                  key={project.projectId}
                  onClick={() => onMoveToProject(project.projectId)}
                  disabled={session.projectId === project.projectId}
                >
                  <FolderOpen className="h-4 w-4 mr-2" />
                  <span className="truncate">{project.name}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>

          <DropdownMenuSeparator />

          <DropdownMenuItem onClick={onDuplicate}>
            <Copy className="h-4 w-4 mr-2" />
            Duplicate
          </DropdownMenuItem>

          <DropdownMenuItem onClick={onExport}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem onClick={onDelete} className="text-destructive focus:text-destructive">
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
