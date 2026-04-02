"use client";

import { useMemo } from "react";
import { DownloadSimple } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataTable, type Column } from "@/components/data-table";
import type { Lead } from "@/types";

interface LeadsTableProps {
  leads: Lead[];
  jobId: string | null;
  onDownloadCsv: (jobId: string) => void;
}

export function LeadsTable({ leads, jobId, onDownloadCsv }: LeadsTableProps) {
  const columns = useMemo<Column<Lead>[]>(
    () => [
      {
        key: "name",
        header: "Name",
        headerClassName: "min-w-[160px]",
        className: "font-medium",
        render: (row) => row.name,
      },
      {
        key: "phone",
        header: "Phone",
        headerClassName: "min-w-[120px]",
        className: "font-mono text-xs",
        render: (row) => row.phone,
      },
      {
        key: "address",
        header: "Address",
        headerClassName: "min-w-[200px]",
        className: "max-w-[250px] truncate",
        render: (row) => <span title={row.address}>{row.address}</span>,
      },
      {
        key: "email",
        header: "Email",
        headerClassName: "min-w-[140px]",
        render: (row) =>
          row.email !== "N/A" ? (
            <a
              href={`mailto:${row.email}`}
              className="text-primary underline-offset-4 hover:underline"
            >
              {row.email}
            </a>
          ) : (
            <span className="text-muted-foreground">N/A</span>
          ),
      },
      {
        key: "category",
        header: "Category",
        headerClassName: "min-w-[100px]",
        render: (row) =>
          row.category !== "N/A" ? (
            <Badge variant="secondary">{row.category}</Badge>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
      {
        key: "website",
        header: "Website",
        headerClassName: "min-w-[100px]",
        render: (row) =>
          row.website !== "N/A" ? (
            <a
              href={row.website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline-offset-4 hover:underline"
            >
              Link
            </a>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
      {
        key: "score",
        header: "Score",
        headerClassName: "w-[60px] text-center",
        className: "text-center font-mono text-xs",
        render: (row) => `${(row.confidence_score * 100).toFixed(0)}%`,
      },
    ],
    [],
  );

  if (leads.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
          <CardDescription>
            Scraped leads will appear here after a run completes.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Results</CardTitle>
            <CardDescription>
              {leads.length} lead{leads.length !== 1 && "s"} scraped
            </CardDescription>
          </div>
          {jobId && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDownloadCsv(jobId)}
            >
              <DownloadSimple data-icon="inline-start" />
              Download CSV
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <DataTable
          data={leads}
          columns={columns}
          pageSize={10}
          maxHeight="480px"
          rowKey={(row, i) => `${row.name}-${row.phone}-${i}`}
          emptyMessage="No leads scraped yet."
        />
      </CardContent>
    </Card>
  );
}
