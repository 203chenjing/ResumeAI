import { redirect } from "next/navigation";
import { ROUTES } from "@/lib/navigation";

export default function KnowledgeRedirectPage() {
  redirect(ROUTES.assets);
}
