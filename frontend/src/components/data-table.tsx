"use client";

import { useMemo, useState, type ReactNode } from "react";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface Column<T> {
  key: string;
  header: string;
  className?: string;
  headerClassName?: string;
  render: (row: T, index: number) => ReactNode;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  pageSize?: number;
  maxHeight?: string;
  rowKey: (row: T, index: number) => string;
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
  emptyMessage?: string;
}

export function DataTable<T>({
  data,
  columns,
  pageSize = 10,
  maxHeight = "480px",
  rowKey,
  onRowClick,
  selectedKey,
  emptyMessage = "No data to display.",
}: DataTableProps<T>) {
  const [page, setPage] = useState(0);
  const safePageSize = Math.max(1, pageSize);
  const totalPages = Math.max(1, Math.ceil(data.length / safePageSize));
  const currentPage = Math.min(page, totalPages - 1);

  const pageData = useMemo(
    () => data.slice(currentPage * safePageSize, (currentPage + 1) * safePageSize),
    [currentPage, data, safePageSize],
  );

  const start = currentPage * safePageSize + 1;
  const end = Math.min((currentPage + 1) * safePageSize, data.length);

  if (data.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div
        className="min-w-0 overflow-auto rounded-md border"
        style={{ maxHeight }}
      >
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col.key} className={col.headerClassName}>
                  {col.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageData.map((row, i) => {
              const globalIndex = currentPage * safePageSize + i;
              const key = rowKey(row, globalIndex);
              return (
                <TableRow
                  key={key}
                  data-state={selectedKey === key ? "selected" : undefined}
                  className={onRowClick ? "cursor-pointer" : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((col) => (
                    <TableCell key={col.key} className={col.className}>
                      {col.render(row, globalIndex)}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between px-1">
          <span className="text-xs text-muted-foreground">
            {start}–{end} of {data.length}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-xs"
              disabled={currentPage === 0}
              onClick={() => setPage(Math.max(0, currentPage - 1))}
            >
              <CaretLeft />
            </Button>
            <span className="min-w-[64px] text-center text-xs text-muted-foreground">
              {currentPage + 1} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="icon-xs"
              disabled={currentPage >= totalPages - 1}
              onClick={() => setPage(Math.min(totalPages - 1, currentPage + 1))}
            >
              <CaretRight />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
