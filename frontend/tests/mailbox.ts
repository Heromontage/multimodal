import {expect,type APIRequestContext} from '@playwright/test';

export function requireTestMailbox(){
  if(!process.env.TEST_MAILBOX_URL)throw Error('Set TEST_MAILBOX_URL to the isolated browser-test API before running tests.');
}
export async function verificationToken(request:APIRequestContext,email:string){
  const mailbox=process.env.TEST_MAILBOX_URL;
  if(!mailbox)throw Error('Run the isolated tests/browser_server.py API and set TEST_MAILBOX_URL. Browser tests must not send real emails.');
  const response=await request.get(`${mailbox}/test-mail/${encodeURIComponent(email)}`);
  expect(response.ok()).toBe(true);
  return (await response.json()).token as string;
}
export async function verifyAndSignin(request:APIRequestContext,email:string,password:string){
  const token=await verificationToken(request,email);
  expect((await request.post('/api/verify-email',{data:{token,password}})).status()).toBe(200);
  expect((await request.post('/api/signin',{data:{email,password}})).status()).toBe(200);
}
