// workspace 状态徽章：status → variant 映射 + 中文标签
import { Badge } from "@/components/ui/badge";
import { STATUS_LABEL, statusToVariant } from "@/lib/workspace";
import type { WorkspaceStatus } from "@/types";

export interface StatusBadgeProps {
  status: WorkspaceStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge variant={statusToVariant(status)} className={className}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}
