import { AuthGate } from "@/components/auth-gate";
import { TaskDashboard } from "@/components/task-dashboard";

export const metadata = { title: "Home | Peach" };

export default function HomePage() {
  return (
    <AuthGate>
      <TaskDashboard />
    </AuthGate>
  );
}
