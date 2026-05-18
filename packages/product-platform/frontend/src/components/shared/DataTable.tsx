import type { ReactNode } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";

export interface DataTableColumn<TItem> {
  header: string;
  cell: (item: TItem) => ReactNode;
}

export function DataTable<TItem>({
  columns,
  items,
  getKey
}: {
  columns: DataTableColumn<TItem>[];
  items: TItem[];
  getKey: (item: TItem) => string;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border/80 bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead key={column.header}>{column.header}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={getKey(item)}>
              {columns.map((column) => (
                <TableCell key={column.header}>{column.cell(item)}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
