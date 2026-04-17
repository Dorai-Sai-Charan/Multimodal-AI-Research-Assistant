"use client";

import { useInitModels } from "@/lib/hooks";

export function ModelsBootstrap() {
  useInitModels();
  return null;
}
