// Features the real Python API serves today. Compare is available in mock mode.
const apiMode = process.env.NEXT_PUBLIC_USE_MOCKS === "0";

export const features = {
  compare: !apiMode,
};
