/**
 * Catch-all proxy to the FastAPI backend.
 * The browser calls /api/<endpoint>; this route forwards to BACKEND_API_URL
 * so the backend can run on a different origin/port without CORS pain.
 */

import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = (process.env.BACKEND_API_URL ?? "http://localhost:8000/api").replace(
  /\/$/,
  "",
);

async function forward(
  req: NextRequest,
  params: Promise<{ path: string[] }>,
): Promise<NextResponse> {
  const { path } = await params;
  const url =
    `${BACKEND}/${path.map(encodeURIComponent).join("/")}` +
    (req.nextUrl.search ?? "");

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };

  if (!["GET", "HEAD"].includes(req.method)) {
    const ab = await req.arrayBuffer();
    if (ab.byteLength) init.body = ab;
  }

  try {
    const res = await fetch(url, init);
    const body = await res.arrayBuffer();
    const outHeaders = new Headers(res.headers);
    outHeaders.delete("content-encoding");
    outHeaders.delete("transfer-encoding");
    return new NextResponse(body, { status: res.status, headers: outHeaders });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      {
        detail: `Backend unreachable at ${BACKEND}. Start it with \`python -m src.main\`. (${msg})`,
      },
      { status: 503 },
    );
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, ctx.params);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, ctx.params);
}
export async function PUT(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, ctx.params);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, ctx.params);
}
export async function PATCH(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, ctx.params);
}
