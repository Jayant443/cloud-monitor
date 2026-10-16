import { useState } from 'react'
import { authApi, setToken, type AuthUser } from '../lib/auth'
import { Icon } from './DashboardUI'

type Mode = 'login' | 'signup'

export function AuthPage({ onAuthed }: { onAuthed: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [identifier, setIdentifier] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const switchMode = (next: Mode) => {
    setMode(next)
    setError('')
  }

  const submit = async () => {
    setError('')
    setBusy(true)
    try {
      if (mode === 'login') {
        const { access_token } = await authApi.login(identifier.trim(), password)
        setToken(access_token)
      } else {
        await authApi.signup({
          username: username.trim(),
          email: email.trim(),
          password,
          ...(displayName.trim() ? { display_name: displayName.trim() } : {}),
        })
        const { access_token } = await authApi.login(username.trim(), password)
        setToken(access_token)
      }
      onAuthed(await authApi.me())
    } catch (cause) {
      setToken(null)
      setError(cause instanceof Error ? cause.message : 'Authentication failed')
    } finally {
      setBusy(false)
    }
  }

  const canSubmit = busy || (mode === 'login'
    ? !identifier.trim() || !password
    : !username.trim() || !email.trim() || !password)

  return <div className="auth-wrap">
    <div className="auth-card panel">
      <div className="auth-brand"><span className="auth-logo"><Icon name="activity" size={18} /></span><span>TheMonitor</span></div>
      <div className="section-kicker">WORKSPACE ACCESS</div>
      <h1>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
      <p className="auth-sub">{mode === 'login' ? 'Sign in to view your infrastructure.' : 'One account per person. Takes a few seconds.'}</p>
      <div className="auth-tabs" role="tablist">
        <button role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')}>Sign in</button>
        <button role="tab" aria-selected={mode === 'signup'} className={mode === 'signup' ? 'active' : ''} onClick={() => switchMode('signup')}>Sign up</button>
      </div>
      {error && <div className="inline-error auth-error">{error}</div>}
      <div className="auth-fields">
        {mode === 'login'
          ? <label className="rule-field"><span>Username or email</span><input value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder="admin" autoComplete="username" /></label>
          : <>
            <label className="rule-field"><span>Username</span><input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" autoComplete="username" /></label>
            <label className="rule-field"><span>Email</span><input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" /></label>
            <label className="rule-field"><span>Display name <em>(optional)</em></span><input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Ops" autoComplete="nickname" /></label>
          </>}
        <label className="rule-field"><span>Password{mode === 'signup' && ' (min 8 characters)'}</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} onKeyDown={(e) => { if (e.key === 'Enter' && !canSubmit) void submit() }} /></label>
      </div>
      <button className="primary-button auth-submit" disabled={canSubmit} onClick={() => void submit()}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
    </div>
  </div>
}
