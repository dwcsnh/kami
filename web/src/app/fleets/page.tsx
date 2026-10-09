import { LoadingState } from "@/manager/LoadingState";
import { Suspense } from "react";
import Page from "@/manager/FleetsPage";
export default function Route() {
  return (
    <Suspense fallback={<LoadingState variant="page"/>}>
      <Page />
    </Suspense>
  );
}
