import { NextRequest, NextResponse } from 'next/server';

const backend = process.env.MODEL_API_URL || 'http://127.0.0.1:8000';
const methods:Record<string,string> = {
  schema:'GET', health:'GET', session:'GET',
  predict:'POST', signup:'POST', signin:'POST', signout:'POST',
};
async function proxy(request: NextRequest, context: { params: Promise<{ endpoint: string }> }) {
  const { endpoint } = await context.params;
  if (!Object.hasOwn(methods,endpoint)) return NextResponse.json({detail:'Not found'}, {status:404});
  if (methods[endpoint] !== request.method) return NextResponse.json({detail:'Method not allowed'}, {status:405});
  if(request.method==='POST'){
    const origin=request.headers.get('origin');
    try{
      if((origin&&new URL(origin).host!==request.headers.get('host'))||request.headers.get('sec-fetch-site')==='cross-site'){
        return NextResponse.json({detail:'This request must come from the assessment app.'},{status:403});
      }
    }catch{return NextResponse.json({detail:'Invalid request origin.'},{status:403});}
  }
  const body = request.method === 'POST' ? await request.text() : undefined;
  if (body && body.length > 65536) return NextResponse.json({detail:'Request too large'}, {status:413});
  try {
    const response = await fetch(`${backend}/${endpoint}`, {method:request.method,
      headers:{'Content-Type':'application/json','Cookie':request.headers.get('cookie')||''},
      body, cache:'no-store', signal:AbortSignal.timeout(20000)});
    const headers=new Headers({'Content-Type':'application/json','Cache-Control':'no-store'});
    for(const cookie of response.headers.getSetCookie())headers.append('Set-Cookie',cookie);
    return new NextResponse(await response.text(), {status:response.status,headers});
  } catch {
    return NextResponse.json({detail:'The account and prediction service is unavailable. Please try again.'}, {status:503});
  }
}
export const GET = proxy;
export const POST = proxy;
