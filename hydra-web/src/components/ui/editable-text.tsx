/**
 * EditableText - Inline editable text component.
 *
 * Allows double-click to edit text inline with keyboard support:
 * - Enter to save
 * - Escape to cancel
 * - Blur to save
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';

export interface EditableTextProps {
  /** Current text value */
  value: string;
  /** Callback when the value is saved */
  onSave: (newValue: string) => void;
  /** Placeholder text when value is empty */
  placeholder?: string;
  /** Class name for the display text span */
  className?: string;
  /** Class name for the input element when editing */
  inputClassName?: string;
  /** Disable editing */
  disabled?: boolean;
  /** Maximum length of the input */
  maxLength?: number;
  /** Minimum length required to save */
  minLength?: number;
  /** Show visual indicator that text is editable */
  showEditHint?: boolean;
}

export function EditableText({
  value,
  onSave,
  placeholder = 'Untitled',
  className,
  inputClassName,
  disabled = false,
  maxLength = 100,
  minLength = 1,
  showEditHint = false,
}: EditableTextProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync editValue with value when not editing
  useEffect(() => {
    if (!isEditing) {
      setEditValue(value);
    }
  }, [value, isEditing]);

  // Focus and select input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleDoubleClick = useCallback(() => {
    if (disabled) return;
    setIsEditing(true);
    setEditValue(value);
  }, [disabled, value]);

  const handleSave = useCallback(() => {
    const trimmedValue = editValue.trim();
    setIsEditing(false);

    // Only save if value meets minimum length and is different
    if (trimmedValue.length >= minLength && trimmedValue !== value) {
      onSave(trimmedValue);
    } else {
      // Reset to original value if empty or unchanged
      setEditValue(value);
    }
  }, [editValue, minLength, value, onSave]);

  const handleCancel = useCallback(() => {
    setIsEditing(false);
    setEditValue(value);
  }, [value]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSave();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        handleCancel();
      }
    },
    [handleSave, handleCancel]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value;
      if (newValue.length <= maxLength) {
        setEditValue(newValue);
      }
    },
    [maxLength]
  );

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type="text"
        value={editValue}
        onChange={handleChange}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className={cn(
          'bg-transparent border-b border-primary outline-none min-w-[100px]',
          'text-inherit font-inherit',
          inputClassName
        )}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-label="Edit text"
      />
    );
  }

  return (
    <span
      onDoubleClick={handleDoubleClick}
      className={cn(
        disabled ? 'cursor-default' : 'cursor-pointer',
        showEditHint && !disabled && 'hover:bg-muted/50 rounded px-1 -mx-1 transition-colors',
        className
      )}
      title={disabled ? undefined : 'Double-click to edit'}
      role={disabled ? undefined : 'button'}
      tabIndex={disabled ? undefined : 0}
      onKeyDown={
        disabled
          ? undefined
          : (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleDoubleClick();
              }
            }
      }
    >
      {value || <span className="text-muted-foreground italic">{placeholder}</span>}
    </span>
  );
}
