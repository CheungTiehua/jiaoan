const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const API_PROXY_TIMEOUT_MS = Number(process.env.API_PROXY_TIMEOUT_MS || 600_000);

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path?: string[] }> | { path?: string[] };
};

async function getPath(context: RouteContext) {
  const params = await context.params;
  return (params.path || []).map(encodeURIComponent).join("/");
}

function makeHeaders(request: Request) {
  const headers = new Headers(request.headers);
  for (const name of [
    "host",
    "connection",
    "content-length",
    "accept-encoding",
    "x-forwarded-host",
    "x-forwarded-port",
    "x-forwarded-proto",
  ]) {
    headers.delete(name);
  }
  return headers;
}

function makeResponseHeaders(upstream: Response) {
  const headers = new Headers();
  for (const [key, value] of upstream.headers) {
    const lower = key.toLowerCase();
    if (["connection", "content-encoding", "content-length", "transfer-encoding"].includes(lower)) {
      continue;
    }
    headers.set(key, value);
  }
  return headers;
}

async function proxy(request: Request, context: RouteContext) {
  const path = await getPath(context);
  const incomingUrl = new URL(request.url);
  const targetUrl = `${BACKEND_URL}/api/${path}${incomingUrl.search}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_PROXY_TIMEOUT_MS);

  try {
    const body = ["GET", "HEAD"].includes(request.method)
      ? undefined
      : await request.arrayBuffer();
    const upstream = await fetch(targetUrl, {
      method: request.method,
      headers: makeHeaders(request),
      body,
      signal: controller.signal,
    });

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: makeResponseHeaders(upstream),
    });
  } catch (error) {
    const message = error instanceof Error && error.name === "AbortError"
      ? "请求超时，请稍后重试"
      : "无法连接到后端服务";
    const status = error instanceof Error && error.name === "AbortError" ? 504 : 502;
    return Response.json({ detail: message }, { status });
  } finally {
    clearTimeout(timeout);
  }
}

export async function GET(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function PUT(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function PATCH(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: Request, context: RouteContext) {
  return proxy(request, context);
}
