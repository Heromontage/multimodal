'use client';
import {useEffect, useState} from 'react';
import {ArrowRight, CircleNotch, Heartbeat} from '@phosphor-icons/react';
import type {AccountSession} from '@/lib/types';
import Workspace from './Workspace';

export default function AuthGate(){
  const [account,setAccount]=useState<AccountSession|null>(null);
  const [checking,setChecking]=useState(true);
  const [mode,setMode]=useState<'signin'|'signup'>('signin');
  const [email,setEmail]=useState('');
  const [password,setPassword]=useState('');
  const [confirmation,setConfirmation]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    fetch('/api/session',{signal:controller.signal,cache:'no-store'}).then(async response=>{
      if(response.status===401)return;
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Unable to load your account.');
      setAccount(data);
    }).catch(e=>{if(e.name!=='AbortError')setError(e.message);})
      .finally(()=>{if(!controller.signal.aborted)setChecking(false);});
    return ()=>controller.abort();
  },[]);
  async function authenticate(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();setError('');
    if(mode==='signup'&&password!==confirmation){setError('The passwords do not match.');return;}
    setBusy(true);
    try{
      const response=await fetch('/api/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Enter a valid email and a password of 8–128 characters.');
      setPassword('');setConfirmation('');setAccount(data);
    }catch(e){setError(e instanceof Error?e.message:'Unable to connect. Please try again.');}
    finally{setBusy(false);}
  }
  async function signout(){
    const response=await fetch('/api/signout',{method:'POST'});
    if(!response.ok)throw Error('Unable to sign out. Please try again.');
    setAccount(null);setError('');setEmail('');setPassword('');setConfirmation('');setMode('signin');
  }
  if(checking)return <div className="loading-shell" role="status"><CircleNotch size={28} className="spin"/><p>Loading your account…</p></div>;
  if(account)return <Workspace key={account.user.email} account={account} onSignout={signout}
    onSessionExpired={()=>{setAccount(null);setPassword('');setError('Your session has expired. Please sign in again.');}}/>;
  return <main className="auth-page">
    <a className="brand auth-brand" href="/" aria-label="Coronary Atlas home"><span className="brand-mark"><Heartbeat size={25} weight="bold"/></span><span>Coronary<span className="brand-light">Atlas</span></span></a>
    <section className="auth-card">
      <span className="tiny-label">YOUR ASSESSMENT WORKSPACE</span>
      <h1>{mode==='signin'?'Welcome back.':'Create your account.'}</h1>
      <p className="auth-intro">{mode==='signin'?'Sign in to return to your saved patient inputs.':'Save your inputs and return to your assessments.'}</p>
      <form onSubmit={authenticate} aria-label={mode==='signin'?'Sign in':'Sign up'}>
        <label htmlFor="auth-email">Email address</label>
        <input id="auth-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/>
        <label htmlFor="auth-password">Password</label>
        <input id="auth-password" type="password" autoComplete={mode==='signin'?'current-password':'new-password'} required minLength={8} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/>
        {mode==='signup'&&<><span className="auth-hint">Use at least 8 characters.</span><label htmlFor="auth-confirm">Confirm password</label><input id="auth-confirm" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={confirmation} onChange={e=>setConfirmation(e.target.value)} disabled={busy}/></>}
        {error&&<p className="auth-error" role="alert">{error}</p>}
        <button className="button primary auth-submit" disabled={busy} type="submit">{busy?<CircleNotch className="spin" size={18}/>:null}{busy?'Please wait…':mode==='signin'?'Sign in':'Create account'}<ArrowRight size={17}/></button>
      </form>
      <p className="auth-switch">{mode==='signin'?'New here?':'Already have an account?'} <button disabled={busy} onClick={()=>{setMode(mode==='signin'?'signup':'signin');setError('');setPassword('');setConfirmation('');}}>{mode==='signin'?'Sign up':'Sign in'}</button></p>
    </section>
    <p className="auth-save-note">Your 55 inputs are saved when you run an assessment.</p>
  </main>;
}
