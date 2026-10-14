'use client';
import {useEffect,useState} from 'react';
import {CircleNotch,Heartbeat} from '@phosphor-icons/react';

export default function VerifyEmail(){
  const [token,setToken]=useState('');
  const [password,setPassword]=useState('');
  const [ready,setReady]=useState(false);
  const [busy,setBusy]=useState(false);
  const [done,setDone]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{
    const value=new URLSearchParams(window.location.hash.slice(1)).get('token');
    if(value){setToken(value);window.history.replaceState(null,'',window.location.pathname);}
    setReady(true);
  },[]);
  async function verify(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();setBusy(true);setError('');
    try{
      const response=await fetch('/api/verify-email',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,password})});
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Unable to verify this link. Request a new verification email.');
      setDone(true);setToken('');setPassword('');
    }catch(e){setError(e instanceof Error?e.message:'Unable to connect. Please try again.');}
    finally{setBusy(false);}
  }
  return <main className="auth-page">
    <a className="brand auth-brand" href="/"><span className="brand-mark"><Heartbeat size={25}/></span><span>Coronary Atlas</span></a>
    <section className="auth-card"><span className="tiny-label">EMAIL VERIFICATION</span>
      <h1>{done?'Email verified.':'Verify your email.'}</h1>
      {done?<><p className="auth-notice" role="status">Your account is ready. Sign in to access your saved inputs.</p><a className="button primary auth-submit" href="/">Continue to sign in</a></>:!ready?<p role="status">Loading verification…</p>:!token?<><p className="auth-error" role="alert">Open the link from your verification email. If it has expired, request a new one from the sign-in page.</p><a className="button secondary" href="/">Back to sign in</a></>:<>
        <p className="auth-intro">Enter the password you chose for this account to confirm your email address.</p>
        <form onSubmit={verify} aria-label="Verify email">
          <label htmlFor="verify-password">Account password</label>
          <input id="verify-password" type="password" autoComplete="current-password" required minLength={8} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/>
          {error&&<p className="auth-error" role="alert">{error}</p>}
          <button className="button primary auth-submit" type="submit" disabled={busy}>{busy?<CircleNotch className="spin" size={18}/>:null}{busy?'Verifying…':'Verify email'}</button>
        </form><p className="auth-switch"><a href="/">Back to sign in / resend email</a></p>
      </>}
    </section>
  </main>;
}
