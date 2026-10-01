import { AuthGate } from "@/components/auth-gate";
import { ItemBoard } from "@/components/item-board";

export const metadata = { title: "Board | Peach" };

export default function ItemsPage() {
  return (
    <AuthGate>
      <ItemBoard />
    </AuthGate>
  );
}
