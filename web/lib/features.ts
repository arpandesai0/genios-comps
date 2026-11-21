// Features the real Python API serves today. In mock mode everything stays visible.
// The real API serves read-only data only for now; comps and manual ingest come later.
const apiMode = process.env.NEXT_PUBLIC_USE_MOCKS === "0";

export const features = {
  compare: !apiMode,
  manualIngest: !apiMode,
};
