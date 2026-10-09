import { LoadingState } from "@/manager/LoadingState";
import { Suspense } from "react";
import VisualizerPage from "@/manager/VisualizerPage";
export default function Page() { return <Suspense fallback={<LoadingState variant="page"/>}><VisualizerPage /></Suspense>; }
