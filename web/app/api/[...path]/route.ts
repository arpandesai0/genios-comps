import { handleMock } from "@/mocks/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
async function handle(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  if (process.env.NEXT_PUBLIC_USE_MOCKS === "0") {
    return Response.json(
      {
        error: {
          code: "not_found",
          message: "Mocks are disabled.",
          details: {},
        },
      },
      { status: 404 },
    );
  }
  return handleMock(request, (await context.params).path.join("/"));
}
export const GET = handle;
export const POST = handle;
