import { notFound } from "next/navigation";
import DataView from "@/components/data-view";

// Keep the /data URL while respecting the repository's blanket data/ ignore.
export const dynamicParams = false;
export function generateStaticParams() {
  return [{ view: "data" }];
}

export default async function WorkspacePage({ params }: PageProps<"/[view]">) {
  if ((await params).view !== "data") notFound();
  return <DataView />;
}
