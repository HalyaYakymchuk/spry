"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, Clock, ListTodo } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

export function TaskDashboard() {
  const { data, isPending } = useQuery({
    queryKey: ["items"],
    queryFn: () => api.listItems({ limit: 100 }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const todoCount = items.filter((item) => item.status === "todo").length;
  const inProgressCount = items.filter(
    (item) => item.status === "in_progress",
  ).length;
  const doneCount = items.filter((item) => item.status === "done").length;
  const progressPercent = total > 0 ? Math.round((doneCount / total) * 100) : 0;

  return (
    <div className="grid gap-8">
      <PageHeader
        icon="🍑"
        title="Dashboard"
        description="Overview of your tasks and progress."
        action={
          <Button asChild size="lg">
            <Link href="/items">
              View board
              <ArrowRight data-icon="inline-end" className="size-4" />
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">To Do</CardTitle>
            <ListTodo className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isPending ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              <div className="text-2xl font-bold">{todoCount}</div>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              Tasks waiting to be started
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <Clock className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isPending ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              <div className="text-2xl font-bold">{inProgressCount}</div>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              Tasks currently being worked on
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle2 className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isPending ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              <div className="text-2xl font-bold">
                {doneCount}{" "}
                <span className="text-xs font-normal text-muted-foreground">
                  ({progressPercent}%)
                </span>
              </div>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              Tasks marked as done
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default TaskDashboard;
