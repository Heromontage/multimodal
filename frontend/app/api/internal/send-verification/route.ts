import {createHash, timingSafeEqual} from 'node:crypto';
import nodemailer from 'nodemailer';

export const runtime = 'nodejs';

function hasValidSecret(request: Request, expected: string): boolean {
  const header = request.headers.get('authorization');
  if (!header?.startsWith('Bearer ')) return false;
  const supplied = createHash('sha256').update(header.slice(7)).digest();
  const configured = createHash('sha256').update(expected).digest();
  return timingSafeEqual(supplied, configured);
}

export async function POST(request: Request) {
  const secret = process.env.MAIL_RELAY_TOKEN;
  if (!secret || secret.length < 32) {
    return Response.json({detail: 'Email relay is unavailable.'}, {status: 503});
  }
  if (!hasValidSecret(request, secret)) {
    return Response.json({detail: 'Unauthorized.'}, {status: 401});
  }

  let recipient: unknown;
  let token: unknown;
  try {
    const body = await request.text();
    if (body.length > 512) return Response.json({detail: 'Request too large.'}, {status: 413});
    ({recipient, token} = JSON.parse(body));
  } catch {
    return Response.json({detail: 'Invalid request.'}, {status: 400});
  }
  if (typeof recipient !== 'string' || recipient.length > 254 ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient) ||
      typeof token !== 'string' || !/^[A-Za-z0-9_-]{32,128}$/.test(token)) {
    return Response.json({detail: 'Invalid request.'}, {status: 400});
  }

  const username = process.env.SMTP_USERNAME?.trim();
  const password = process.env.SMTP_PASSWORD?.replace(/\s/g, '');
  if (!username || !password) {
    return Response.json({detail: 'Email relay is unavailable.'}, {status: 503});
  }

  const link = new URL('/verify-email', request.url);
  link.hash = `token=${token}`;
  try {
    const transport = nodemailer.createTransport({
      host: 'smtp.gmail.com', port: 465, secure: true,
      auth: {user: username, pass: password},
      connectionTimeout: 10_000, greetingTimeout: 10_000, socketTimeout: 10_000,
    });
    await transport.sendMail({
      from: username,
      to: recipient,
      subject: 'Verify your email for Coronary Atlas',
      text: 'Confirm your email address for Coronary Atlas.\n\n' +
        `${link.toString()}\n\n` +
        'This link expires in 30 minutes and can be used once. ' +
        'Enter your account password on the verification page, then sign in.\n\n' +
        'If you did not request this account, ignore this email. ' +
        'Your address will remain unverified.\n',
    });
    return Response.json({status: 'sent'}, {headers: {'Cache-Control': 'no-store'}});
  } catch {
    return Response.json({detail: 'Unable to send verification email.'}, {status: 503});
  }
}
