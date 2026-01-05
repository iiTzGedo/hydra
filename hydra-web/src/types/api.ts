// Generic API response wrapper
export interface ApiResponse<T> {
  data: T;
  meta?: PaginationMeta;
}

// Pagination metadata
export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
}

// Paginated list response (for list endpoints)
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// Generic API error response
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  requestId?: string;
}

// Common query parameters
export interface PaginationParams {
  limit?: number;
  offset?: number;
}

export interface SortParams {
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface SearchParams {
  search?: string;
}

// Combined list params
export type ListParams = PaginationParams & SortParams & SearchParams;
