import { NextRequest, NextResponse } from 'next/server';

const backend = process.env.MODEL_API_URL || 'http://127.0.0.1:8000';
async function proxy(request: NextRequest, context: { params: Promise<{ endpoint: string }> }) {
  const { endpoint } = await context.params;
  if (!['schema', 'predict', 'health'].includes(endpoint)) return NextResponse.json({detail:'Not found'}, {status:404});
  if ((endpoint === 'predict') !== (request.method === 'POST')) return NextResponse.json({detail:'Method not allowed'}, {status:405});
  const body = request.method === 'POST' ? await request.text() : undefined;
  if (body && body.length > 65536) return NextResponse.json({detail:'Request too large'}, {status:413});
  try {
    const response = await fetch(`${backend}/${endpoint}`, {method:request.method,
      headers:{'Content-Type':'application/json'}, body, cache:'no-store', signal:AbortSignal.timeout(20000)});
    return new NextResponse(await response.text(), {status:response.status,
      headers:{'Content-Type':'application/json', 'Cache-Control':'no-store'}});
  } catch {
    return NextResponse.json({detail:'The prediction service is unavailable. Start the API and try again.'}, {status:503});
  }
}
export const GET = proxy;
export const POST = proxy;
