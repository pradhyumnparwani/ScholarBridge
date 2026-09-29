import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { ArrowRight, Bell, BookOpen, Check, CheckCircle2, ChevronLeft, CircleAlert, ClipboardCheck, FileCheck2, FileText, Home, LogOut, Menu, Search, ShieldCheck, UserRound, X } from 'lucide-react'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const flow = ['Discover', 'Check', 'Apply', 'Verify', 'Detect Deficiency', 'Review', 'Track']
type User = { id: number; email: string; full_name: string; role: string }
type Profile = { category: string; income: number; age: number; education_level: string; course: string; percentage: number; phone?: string; state?: string; district?: string }
type Scholarship = { id: number; name: string; slug: string; level: string; benefit: string; description?: string; deadline: string; is_active: boolean }
type Rule = { id: number; field: string; operator: string; value: string; description: string }
type SchemeDetail = Scholarship & { source_url?: string; academic_year?: string; source_name?: string; rules: Rule[]; required_documents: { id: number; document_type: string; label: string; required: boolean }[] }
type Application = { id: number; status: string; scheme_id: number; title: string; summary?: string; deficiencies?: number; documents_total?: number; documents_verified?: number }
type AppDetail = Application & { documents: DocumentItem[]; deficiencies: Deficiency[]; timeline: Timeline[] }
type DocumentItem = { id: number; document_type: string; filename: string; verification_status: string; verification_summary?: string; extracted_data?: Record<string, unknown>; created_at?: string }
type Deficiency = { id: number; title: string; description: string; severity: string; field?: string; deficiency_type?: string; reason?: string; required_action?: string; status?: string }
type Timeline = { id: number; status: string; comment?: string; created_at: string }
type Notification = { id: number; title: string; message: string; is_read: boolean; created_at: string }
type Eligibility = { eligible: boolean; summary: string; checks: { rule: string; passed: boolean; actual?: string | number; value: string; explanation?: string }[] }

async function api<T>(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers); const token = localStorage.getItem('scholarshipsetu_token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const selected = applicantSelection()
  const requestPath = path.startsWith('/api/eligibility/check') && selected?.type === 'beneficiary'
    ? `${path}${path.includes('?') ? '&' : '?'}beneficiary_id=${selected.id}`
    : path
  const response = await fetch(`${API}${requestPath}`, { ...options, headers })
  if (!response.ok) { const body = await response.json().catch(() => ({})) as { detail?: string }; throw new Error(body.detail || 'Request failed.') }
  return response.json() as Promise<T>
}
function go(path: string) { window.location.hash = path }
type Beneficiary = Profile & { id: number; full_name: string; institution?: string; relationship_to_applicant?: string }
function applicantSelection() { try { return JSON.parse(localStorage.getItem('scholar_bridge_applicant') || 'null') as { type: 'self' | 'beneficiary'; id?: number; name?: string } | null } catch { return null } }
function Button({ children, variant = 'primary', onClick, type = 'button', disabled = false }: { children: ReactNode; variant?: 'primary' | 'secondary' | 'quiet'; onClick?: () => void; type?: 'button' | 'submit'; disabled?: boolean }) { return <button type={type} className={`button ${variant}`} onClick={onClick} disabled={disabled}>{children}</button> }
function Brand({ compact = false }: { compact?: boolean }) { return <button className="brand" onClick={() => go('/')}><span className="brand-mark">S</span>{!compact && <span><strong>Scholar Bridge</strong><small>AI-assisted, rule-transparent prototype</small></span>}</button> }

function App() {
  const [route, setRoute] = useState(location.hash.slice(1) || '/')
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const change = () => setRoute(location.hash.slice(1) || '/')
    addEventListener('hashchange', change)
    const token = localStorage.getItem('scholarshipsetu_token')

    if (token) {
      api<User>('/api/me')
        .then(setUser)
        .catch(() => {
          localStorage.removeItem('scholarshipsetu_token')
          setUser(null)
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }

    return () => removeEventListener('hashchange', change)
  }, [])

  if (loading) return <div className="loading-screen">Loading Scholar Bridge...</div>

  const logout = () => {
    localStorage.removeItem('scholarshipsetu_token')
    localStorage.removeItem('scholar_bridge_applicant')
    setUser(null)
    go('/')
  }

  if (route === '/') return <Landing user={user} />

  if (route.startsWith('/login')) {
    const next = new URLSearchParams(route.split('?')[1] || '').get('next') || '/dashboard'
    return <Login onLogin={setUser} next={next} />
  }

  if (route === '/signup') return <Signup onLogin={setUser} />

  // Scholarship discovery and scholarship details are intentionally public.
  if (route === '/discover' && !user) return <PublicPortal><Discover /></PublicPortal>
  if (route.startsWith('/scholarship/') && !user) {
    return <PublicPortal><ScholarshipDetails id={Number(route.split('/')[2])} /></PublicPortal>
  }

  // Everything below this point requires an authenticated account.
  if (!user) {
    go(`/login?next=${encodeURIComponent(route)}`)
    return <div className="loading-screen">Redirecting to sign in...</div>
  }

  if (route.startsWith('/admin') && user.role !== 'admin') {
    return <div className="portal-main"><ErrorState text="Officer access is required for this page." /><Button variant="secondary" onClick={() => go('/dashboard')}>Return to dashboard</Button></div>
  }

  if (route === '/who') return <ApplicantChooser next="/dashboard" />
  if (route.startsWith('/beneficiary/new')) {
    return <BeneficiaryForm next={new URLSearchParams(route.split('?')[1] || '').get('next') || '/dashboard'} />
  }

  return <Portal user={user} route={route} logout={logout} />
}
function Landing({ user }: { user: User | null }) {
  return (
    <div className="site-shell">
      <header className="topbar">
        <Brand />

        <nav>
          <a href="#/discover">Discover</a>
          <a href="#/eligibility">Check eligibility</a>
          <a href="#/applications">Applications</a>
        </nav>

        <div>
          {user ? (
            <Button onClick={() => go('/dashboard')}>
              Open dashboard <ArrowRight size={16} />
            </Button>
          ) : (
            <Button onClick={() => go('/login')}>
              Sign in <ArrowRight size={16} />
            </Button>
          )}
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">Scholarship readiness & document verification</div>

            <h1>Get scholarship-ready before you apply.</h1>

            <p>
              Discover opportunities, understand your eligibility, submit
              documents, and track applications through one transparent
              workflow designed for Scheduled Tribe students.
            </p>

            <div className="hero-actions">
              <Button onClick={() => go('/discover')}>
                Explore scholarships <ArrowRight size={17} />
              </Button>

              <Button
                variant="secondary"
                onClick={() => go(user ? '/eligibility' : '/login')}
              >
                Check eligibility <ShieldCheck size={17} />
              </Button>
            </div>

            <div className="workflow">
              {flow.map((item, index) => (
                <span key={item}>
                  <b>{String(index + 1).padStart(2, '0')}</b>
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div className="hero-board">
            <div className="board-heading">
              <span className="live-dot" />
              Transparent eligibility engine
              <ShieldCheck size={18} />
            </div>

            <div className="eligibility-result">
              <div>
                <CheckCircle2 size={19} />
                <strong>ELIGIBLE</strong>
              </div>

              <span>Tribal Higher Education Support Scheme</span>

              <ul>
                <li>
                  <Check size={15} />
                  Category: ST
                </li>
                <li>
                  <Check size={15} />
                  Academic score: 85%+
                </li>
                <li>
                  <Check size={15} />
                  Income: Within scheme limit
                </li>
                <li>
                  <Check size={15} />
                  Education level: Undergraduate
                </li>
              </ul>
            </div>

            <div className="board-footer">
              <ShieldCheck size={17} />
              Every eligibility decision is backed by visible rules.
            </div>
          </div>
        </section>

        <section className="trust-strip">
          <div>
            <strong>Rule-transparent</strong>
            <span>Eligibility logic is visible and explainable.</span>
          </div>

          <div>
            <strong>Document-aware</strong>
            <span>Track uploads, verification and deficiencies.</span>
          </div>

          <div>
            <strong>Officer-ready</strong>
            <span>Designed for transparent scholarship review.</span>
          </div>
        </section>

        <section className="section-band">
          <div className="section-intro">
            <div className="eyebrow">How Scholarship Bridge works</div>
            <h2>From discovery to a ready-to-apply result, without the guesswork.</h2>
            <p>
              Scholarship Bridge connects students and scholarship officers
              through a structured workflow where eligibility, documents and
              application status remain easy to understand.
            </p>
          </div>

          <div className="feature-grid">
            <Feature
              icon={<Search size={21} />}
              title="Discover opportunities"
              text="Find active scholarship and fellowship schemes using study level, benefits and other relevant information."
            />

            <Feature
              icon={<ClipboardCheck size={21} />}
              title="Understand eligibility"
              text="Check your profile against published rules and see exactly which requirements pass or need attention."
            />

            <Feature
              icon={<FileCheck2 size={21} />}
              title="Apply and track"
              text="Upload documents, resolve deficiencies and complete your pre-application verification before applying on the official portal."
            />
          </div>
        </section>
      </main>

      <footer>
        <span>Scholar Bridge · AI-assisted, rule-transparent prototype</span>
        <span>Built for transparent scholarship management</span>
      </footer>
    </div>
  )
}
function Feature({ icon, title, text }: { icon: ReactNode; title: string; text: string }) { return <div className="feature"><div className="feature-icon">{icon}</div><h3>{title}</h3><p>{text}</p></div> }
function Login({ onLogin, next = '/dashboard' }: { onLogin: (user: User) => void; next?: string }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const token = await api<{ access_token: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password }),
      })
      localStorage.setItem('scholarshipsetu_token', token.access_token)
      const currentUser = await api<User>('/api/me')
      onLogin(currentUser)
      go(next || '/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-aside">
        <Brand />
        <div>
          <div className="eyebrow">Student portal</div>
          <h1>Make your next opportunity easier to reach.</h1>
          <p>One transparent workflow for scholarships and fellowships designed for Scheduled Tribe students.</p>
        </div>
        <div className="auth-note"><ShieldCheck size={18} /> Your eligibility is explained, not guessed.</div>
      </div>

      <div className="auth-panel">
        <button className="back-link" onClick={() => go('/')}>
          <ChevronLeft size={17} /> Back to home
        </button>

        <form className="auth-form" onSubmit={submit}>
          <div className="eyebrow">Scholar Bridge</div>
          <h2>Welcome back</h2>
          <p className="muted">Sign in to continue your scholarship journey.</p>

          <label>
            Email address
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required />
          </label>

          <label>
            Password
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your password" required />
          </label>

          {error && <div className="error-message"><CircleAlert size={16} />{error}</div>}

          <Button type="submit" disabled={busy}>
            {busy ? 'Signing in...' : 'Sign in'} <ArrowRight size={17} />
          </Button>

          <p className="auth-switch">
            New to Scholar Bridge? <button type="button" className="text-button" onClick={() => go('/signup')}>Create an account</button>
          </p>
        </form>
      </div>
    </div>
  )
}

function Signup({ onLogin }: { onLogin: (user: User) => void }) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    confirm_password: '',
    age: '',
    category: 'ST',
    income: '',
    education_level: 'UG',
    course: '',
    percentage: '',
    phone: '',
    state: '',
    district: '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const update = (key: keyof typeof form, value: string) => {
    setForm(current => ({ ...current, [key]: value }))
    setError('')
  }

  const continueAccount = (event: FormEvent) => {
    event.preventDefault()
    if (!form.full_name.trim() || !form.email.trim() || !form.password) {
      setError('Please complete all account fields.')
      return
    }
    if (form.password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    if (form.password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }
    setStep(2)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')

    const required = ['age', 'income', 'course', 'percentage', 'phone', 'state', 'district']
    if (required.some(key => !form[key as keyof typeof form])) {
      setError('Please complete your basic student profile.')
      return
    }

    setBusy(true)
    try {
      const token = await api<{ access_token: string }>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          full_name: form.full_name.trim(),
          email: form.email.trim(),
          password: form.password,
          role: 'student',
        }),
      })

      localStorage.setItem('scholarshipsetu_token', token.access_token)

      await api('/api/students/profile', {
        method: 'POST',
        body: JSON.stringify({
          category: form.category,
          age: Number(form.age),
          income: Number(form.income),
          education_level: form.education_level,
          course: form.course.trim(),
          percentage: Number(form.percentage),
          phone: form.phone.trim(),
          state: form.state.trim(),
          district: form.district.trim(),
        }),
      })

      const currentUser = await api<User>('/api/me')
      onLogin(currentUser)
      go('/dashboard')
    } catch (err) {
      localStorage.removeItem('scholarshipsetu_token')
      setError(err instanceof Error ? err.message : 'Unable to create your account.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-aside">
        <Brand />
        <div>
          <div className="eyebrow">Create your student account</div>
          <h1>Start your scholarship journey with a profile that belongs to you.</h1>
          <p>Your account and student details are saved separately so your progress can continue when you return.</p>
        </div>
        <div className="auth-note"><ShieldCheck size={18} /> Your eligibility is based on visible scholarship rules.</div>
      </div>

      <div className="auth-panel">
        <button className="back-link" onClick={() => go('/login')}>
          <ChevronLeft size={17} /> Back to sign in
        </button>

        <form className="auth-form" onSubmit={step === 1 ? continueAccount : submit}>
          <div className="eyebrow">Step {step} of 2</div>
          <h2>{step === 1 ? 'Create your account' : 'Tell us about yourself'}</h2>
          <p className="muted">{step === 1 ? 'These details are used to create your login.' : 'These details help Scholar Bridge check scholarship eligibility.'}</p>

          {step === 1 ? (
            <>
              <label>Full name<input value={form.full_name} onChange={e => update('full_name', e.target.value)} placeholder="Your full name" required /></label>
              <label>Email address<input type="email" value={form.email} onChange={e => update('email', e.target.value)} placeholder="you@example.com" required /></label>
              <label>Password<input type="password" value={form.password} onChange={e => update('password', e.target.value)} placeholder="At least 6 characters" required /></label>
              <label>Confirm password<input type="password" value={form.confirm_password} onChange={e => update('confirm_password', e.target.value)} placeholder="Re-enter your password" required /></label>
            </>
          ) : (
            <div className="form-grid">
              <label>Age<input type="number" min="1" max="100" value={form.age} onChange={e => update('age', e.target.value)} required /></label>
              <label>Category<select value={form.category} onChange={e => update('category', e.target.value)}><option value="ST">ST</option><option value="SC">SC</option><option value="OBC">OBC</option><option value="General">General</option></select></label>
              <label>Annual family income (Rs.)<input type="number" min="0" value={form.income} onChange={e => update('income', e.target.value)} required /></label>
              <label>Education level<select value={form.education_level} onChange={e => update('education_level', e.target.value)}><option value="UG">Undergraduate</option><option value="PG">Postgraduate</option><option value="Diploma">Diploma</option><option value="12th">Class 12</option></select></label>
              <label>Course<input value={form.course} onChange={e => update('course', e.target.value)} placeholder="e.g. B.Tech CSE" required /></label>
              <label>Academic percentage<input type="number" min="0" max="100" step="0.01" value={form.percentage} onChange={e => update('percentage', e.target.value)} required /></label>
              <label>Phone<input type="tel" value={form.phone} onChange={e => update('phone', e.target.value)} placeholder="10-digit mobile number" required /></label>
              <label>State<input value={form.state} onChange={e => update('state', e.target.value)} placeholder="State" required /></label>
              <label>District<input value={form.district} onChange={e => update('district', e.target.value)} placeholder="District" required /></label>
            </div>
          )}

          {error && <div className="error-message"><CircleAlert size={16} />{error}</div>}

          {step === 2 && (
            <Button variant="quiet" onClick={() => setStep(1)}>Back</Button>
          )}

          <Button type="submit" disabled={busy}>
            {busy ? 'Creating account...' : step === 1 ? 'Continue' : 'Create account'} <ArrowRight size={17} />
          </Button>

          {step === 1 && <p className="auth-switch">Already have an account? <button type="button" className="text-button" onClick={() => go('/login')}>Sign in</button></p>}
        </form>
      </div>
    </div>
  )
}

function PublicPortal({ children }: { children: ReactNode }) {
  return (
    <div className="portal">
      <header className="portal-header">
        <Brand />
        <nav>
          <Nav href="/discover" label="Discover" icon={<Search size={17} />} active={location.hash.startsWith('#/discover') || location.hash.startsWith('#/scholarship')} />
          <a className="nav-item" href="#/login"><UserRound size={17} /> Sign in</a>
          <a className="nav-item" href="#/signup"><ArrowRight size={17} /> Sign up</a>
        </nav>
      </header>
      <main className="portal-main">{children}</main>
    </div>
  )
}

function StudentPortal({ user, route, logout }: { user: User; route: string; logout: () => void }) { const [open, setOpen] = useState(false); const [notifications, setNotifications] = useState<Notification[]>([]); const page = route.split('/')[1] || 'dashboard'; useEffect(() => { api<Notification[]>('/api/notifications').then(setNotifications).catch(() => setNotifications([])) }, [route]); const unread = notifications.filter(n => !n.is_read).length; return <div className="portal"><header className="portal-header"><Brand /><button className="mobile-menu" onClick={() => setOpen(!open)}><Menu /></button><nav className={open ? 'open' : ''}><Nav href="/dashboard" label="Dashboard" icon={<Home size={17} />} active={page === 'dashboard'} /><Nav href="/discover" label="Discover" icon={<Search size={17} />} active={page === 'discover' || page === 'scholarship'} /><Nav href="/applications" label="Applications" icon={<FileText size={17} />} active={page === 'applications' || page === 'application'} /><Nav href="/profile" label="Profile" icon={<UserRound size={17} />} active={page === 'profile'} /><Nav href="/notifications" label="Notifications" icon={<Bell size={17} />} active={page === 'notifications'} badge={unread} /></nav><div className="user-menu"><span className="avatar">{user.full_name[0]}</span><span className="user-name">{user.full_name}</span><button className="icon-button" onClick={logout} title="Sign out"><LogOut size={17} /></button></div></header><main className="portal-main">{route === '/dashboard' && <Dashboard user={user} notifications={notifications} />} {route === '/discover' && <Discover />} {route.startsWith('/scholarship/') && <ScholarshipDetails id={Number(route.split('/')[2])} />} {route.startsWith('/apply/') && <CreateApplication id={Number(route.split('/')[2])} />} {route === '/eligibility' && <Eligibility />} {route === '/profile' && <Profile user={user} />} {route === '/applications' && <Applications />} {route.startsWith('/application/') && <ApplicationPage id={Number(route.split('/')[2])} />} {route === '/notifications' && <Notifications items={notifications} markRead={id => api(`/api/notifications/${id}/read`, { method: 'POST' }).then(() => setNotifications(items => items.map(item => item.id === id ? { ...item, is_read: true } : item)))} />}</main></div> }
void StudentPortal
function Portal({ user, route, logout }: { user: User; route: string; logout: () => void }) { const [open, setOpen] = useState(false); const [notifications, setNotifications] = useState<Notification[]>([]); const page = route.split('/')[1] || 'dashboard'; useEffect(() => { api<Notification[]>('/api/notifications').then(setNotifications).catch(() => setNotifications([])) }, [route]); const unread = notifications.filter(n => !n.is_read).length; if (route.startsWith('/admin')) return <AdminPortal user={user} route={route} logout={logout} />; return <div className="portal"><header className="portal-header"><Brand /><button className="mobile-menu" onClick={() => setOpen(!open)}><Menu /></button><nav className={open ? 'open' : ''}><Nav href="/dashboard" label="Dashboard" icon={<Home size={17} />} active={page === 'dashboard'} /><Nav href="/discover" label="Discover" icon={<Search size={17} />} active={page === 'discover' || page === 'scholarship'} /><Nav href="/applications" label="Applications" icon={<FileText size={17} />} active={page === 'applications' || page === 'application'} /><Nav href="/profile" label="Profile" icon={<UserRound size={17} />} active={page === 'profile'} /><Nav href="/notifications" label="Notifications" icon={<Bell size={17} />} active={page === 'notifications'} badge={unread} /></nav><div className="user-menu"><span className="avatar">{user.full_name[0]}</span><span className="user-name">{user.full_name}</span><button className="icon-button" onClick={logout} title="Sign out"><LogOut size={17} /></button></div></header><main className="portal-main">{route === '/dashboard' && <Dashboard user={user} notifications={notifications} />} {route === '/discover' && <Discover />} {route.startsWith('/scholarship/') && <ScholarshipDetails id={Number(route.split('/')[2])} />} {route.startsWith('/apply/') && <CreateApplication id={Number(route.split('/')[2])} />} {route === '/eligibility' && <Eligibility />} {route === '/profile' && <Profile user={user} />} {route === '/applications' && <Applications />} {route.startsWith('/application/') && <ApplicationPage id={Number(route.split('/')[2])} />} {route === '/notifications' && <Notifications items={notifications} markRead={id => api(`/api/notifications/${id}/read`, { method: 'POST' }).then(() => setNotifications(items => items.map(item => item.id === id ? { ...item, is_read: true } : item)))} />}</main></div> }
function Nav({ href, label, icon, active, badge }: { href: string; label: string; icon: ReactNode; active: boolean; badge?: number }) { return <a className={active ? 'nav-item active' : 'nav-item'} href={`#${href}`}>{icon}{label}{badge ? <b className="badge">{badge}</b> : null}</a> }
function Title({ eyebrow, title, text, action }: { eyebrow: string; title: string; text?: string; action?: ReactNode }) { return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{text && <p>{text}</p>}</div>{action}</div> }
function Loading() { return <div className="loading-inline">Loading your information...</div> }
function ErrorState({ text }: { text: string }) { return <div className="error-state"><CircleAlert size={24} /><h2>Access unavailable</h2><p>{text}</p></div> }
function ApplicantChooser({ next }: { next: string }) { const chooseSelf = () => { localStorage.setItem('scholar_bridge_applicant', JSON.stringify({ type: 'self', name: 'My profile' })); go(next) }; return <div className="center-panel applicant-chooser"><div className="feature-icon"><UserRound size={24} /></div><div className="eyebrow">Applicant selection</div><h1>Who are you checking scholarships for?</h1><p>Choose the person whose information will be used for eligibility and document checks.</p><div className="chooser-options"><button onClick={chooseSelf}><strong>Myself</strong><small>I'm looking for scholarships for me.</small></button><button onClick={() => go(`/beneficiary/new?next=${encodeURIComponent(next)}`)}><strong>Someone else</strong><small>I'm helping another person find scholarships.</small></button></div></div> }
function BeneficiaryForm({ next }: { next: string }) { const [form, setForm] = useState({ full_name: 'Aditi Sharma', age: '20', category: 'ST', income: '76000', education_level: 'UG', course: 'B.Tech', percentage: '85.5', institution: '', state: 'Odisha', district: 'Mayurbhanj', relationship_to_applicant: 'Parent / Guardian' }); const update = (key: string, value: string) => setForm({ ...form, [key]: value }); const save = async (event: FormEvent) => { event.preventDefault(); const beneficiary = await api<Beneficiary>('/api/beneficiaries', { method: 'POST', body: JSON.stringify({ ...form, age: Number(form.age), income: Number(form.income), percentage: Number(form.percentage) }) }); localStorage.setItem('scholar_bridge_applicant', JSON.stringify({ type: 'beneficiary', id: beneficiary.id, name: beneficiary.full_name })); go(next) }; return <div className="center-panel beneficiary-form"><button className="back-link" onClick={() => go('/who')}><ChevronLeft size={17} /> Back</button><div className="eyebrow">Applicant / Beneficiary</div><h1>Tell us about the person you are helping.</h1><p>Eligibility and document matching will use this person's information, not the helper's profile.</p><form onSubmit={save}><div className="form-grid">{[['full_name','Full name'],['age','Age'],['category','Category'],['income','Family income'],['education_level','Education level'],['course','Course'],['percentage','Academic percentage'],['institution','Institution'],['state','State'],['district','District']].map(([key,label]) => <label key={key}>{label}<input value={form[key as keyof typeof form]} onChange={event => update(key, event.target.value)} required={key !== 'institution'} /></label>)}</div><label>Relationship to applicant<select value={form.relationship_to_applicant} onChange={event => update('relationship_to_applicant', event.target.value)}>{['Parent / Guardian','Sibling','Teacher / Faculty','Friend','Authorized representative','Other'].map(item => <option key={item}>{item}</option>)}</select></label><Button type="submit">Continue with beneficiary <ArrowRight size={17} /></Button></form></div> }
function Empty({ text }: { text: string }) { return <div className="empty-state"><BookOpen size={25} /><p>{text}</p></div> }
function Status({ value }: { value: string }) { return <span className={`status-badge ${value.toLowerCase().replaceAll(' ', '-')}`}>{value}</span> }
function Dashboard({ user, notifications }: { user: User; notifications: Notification[] }) { const [profile, setProfile] = useState<Profile | null>(null); const [apps, setApps] = useState<Application[]>([]); useEffect(() => { Promise.all([api<Profile>('/api/students/profile'), api<Application[]>('/api/applications')]).then(([p, a]) => { setProfile(p); setApps(a) }) }, []); return <><Title eyebrow="Student dashboard" title={`Good to see you, ${user.full_name.split(' ')[0]}.`} text="Keep your scholarship journey moving from one clear workspace." action={<Button onClick={() => go('/discover')}>Find scholarships <ArrowRight size={17} /></Button>} /><div className="dashboard-grid"><div className="main-column"><section className="welcome-panel"><div><span className="panel-label">Your readiness</span><h2>{profile?.state ? 'Profile ready for matching' : 'Complete your profile to begin'}</h2><p>{profile?.state ? `We can match you with schemes for ${profile.course} in ${profile.state}.` : 'Add your education, income, and location details for accurate eligibility checks.'}</p></div><div className="readiness-ring">{profile?.state ? '100%' : '40%'}</div><Button variant="secondary" onClick={() => go('/profile')}>{profile?.state ? 'Review profile' : 'Complete profile'}</Button></section><section className="content-section"><div className="section-heading"><div><div className="eyebrow">In progress</div><h2>My applications</h2></div><a href="#/applications">View all <ArrowRight size={15} /></a></div>{apps.length ? <div className="application-list">{apps.slice(0, 3).map(app => <ApplicationRow key={app.id} app={app} />)}</div> : <Empty text="Your applications will appear here once you start one." />}</section></div><aside className="side-column"><section className="side-card"><div className="section-heading"><h3>Notifications</h3><a href="#/notifications">View all</a></div>{notifications.slice(0, 3).map(item => <div className="notification compact" key={item.id}><span className="notification-dot" /><div><strong>{item.title}</strong><p>{item.message}</p></div></div>)}{!notifications.length && <Empty text="You are all caught up." />}</section><section className="side-card action-card"><div className="feature-icon"><ClipboardCheck size={20} /></div><h3>Check eligibility</h3><p>Use your profile to see the rules behind every result.</p><Button variant="secondary" onClick={() => go('/eligibility')}>Run a check <ArrowRight size={16} /></Button></section></aside></div></> }
function ApplicationRow({ app }: { app: Application }) { return <button className="application-row" onClick={() => go(`/application/${app.id}`)}><span className="application-icon"><FileText size={19} /></span><span className="application-info"><strong>{app.title}</strong><small>Application #{app.id} · {app.summary || 'Your application is in progress.'}</small>{app.deficiencies ? <em className="action-hint">{app.deficiencies} action{app.deficiencies === 1 ? '' : 's'} required</em> : app.documents_total ? <em className="progress-hint">{app.documents_verified || 0}/{app.documents_total} documents verified</em> : null}</span><Status value={app.status} /><ArrowRight size={17} /></button> }
function Discover() {
  const [schemes, setSchemes] = useState<Scholarship[]>([])
  const [query, setQuery] = useState('')
  const [level, setLevel] = useState('All levels')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    api<Scholarship[]>('/api/scholarships')
      .then(setSchemes)
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load scholarships.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = schemes.filter(s =>
    `${s.name} ${s.benefit} ${s.level}`.toLowerCase().includes(query.toLowerCase()) &&
    (level === 'All levels' || s.level === level)
  )

  return (
    <>
      <Title
        eyebrow="Discovery"
        title="Find your scholarship."
        text="Explore active schemes and understand what each one supports before you apply."
        action={<Button variant="secondary" onClick={() => go('/eligibility')}><ClipboardCheck size={17} /> Check eligibility</Button>}
      />

      <div className="search-controls">
        <label className="search-box"><Search size={18} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search schemes, benefits, or study level" /></label>
        <select value={level} onChange={e => setLevel(e.target.value)}>
          <option>All levels</option>
          <option>Undergraduate</option>
          <option>Post-Matric</option>
          <option>Higher Education</option>
          <option>Postgraduate</option>
        </select>
      </div>

      {loading ? <Loading /> :
        error ? <ErrorState text={`Scholarships could not be loaded: ${error}`} /> :
        filtered.length ? <div className="scheme-grid">{filtered.map(s => <SchemeCard key={s.id} scheme={s} />)}</div> :
        <Empty text={schemes.length ? "No scholarships match those filters." : "No scholarship records are available yet."} />
      }
    </>
  )
}

function SchemeCard({ scheme }: { scheme: Scholarship }) { return <article className="scheme-card"><div className="scheme-top"><span className="level-tag">{scheme.level}</span><span className="deadline">Due {new Date(scheme.deadline).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</span></div><h2>{scheme.name}</h2><p>{scheme.description || scheme.benefit}</p><div className="scheme-benefit"><span>Benefit</span><strong>{scheme.benefit}</strong></div><button className="text-button" onClick={() => go(`/scholarship/${scheme.id}`)}>View details <ArrowRight size={15} /></button></article> }
function ScholarshipDetails({ id }: { id: number }) {
  const [scheme, setScheme] = useState<SchemeDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setScheme(null)
    setError('')
    api<SchemeDetail>(`/api/scholarships/${id}`)
      .then(setScheme)
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load this scholarship.'))
  }, [id])

  if (error) return <><button className="back-link portal-back" onClick={() => go('/discover')}><ChevronLeft size={17} /> Back to discovery</button><ErrorState text={`This scholarship could not be loaded: ${error}`} /></>
  if (!scheme) return <Loading />

  return (
    <>
      <button className="back-link portal-back" onClick={() => go('/discover')}><ChevronLeft size={17} /> Back to discovery</button>
      <div className="detail-hero">
        <div>
          <span className="level-tag">{scheme.level}</span>
          <h1>{scheme.name}</h1>
          <p>{scheme.description}</p>
        </div>
        <div className="detail-cta">
          <span>Application deadline</span>
          <strong>{new Date(scheme.deadline).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}</strong>
          <Button onClick={() => go(`/apply/${scheme.id}`)}>Start application <ArrowRight size={17} /></Button>
        </div>
      </div>
      <div className="detail-grid">
        <section className="content-section">
          <div className="section-heading"><div><div className="eyebrow">Visible rules</div><h2>Eligibility requirements</h2></div><ShieldCheck size={22} /></div>
          {scheme.rules.length ? scheme.rules.map(rule => <div className="rule" key={rule.id}><span className="rule-check"><Check size={16} /></span><div><strong>{rule.description}</strong><small>Checks {rule.field} · {rule.operator} · {rule.value}</small></div></div>) : <Empty text="No eligibility rules have been published for this scheme yet." />}
        </section>
        <section className="content-section">
          <div className="section-heading"><div><div className="eyebrow">Prepare early</div><h2>Required documents & verification</h2></div><FileCheck2 size={22} /></div>
          {scheme.required_documents.length ? scheme.required_documents.map(doc => <div className="document-row" key={doc.id}><div className="document-label"><FileText size={18} /><span><strong>{doc.label}</strong><small>{doc.required ? 'Required' : 'Optional'}</small></span></div></div>) : <Empty text="No document requirements have been published yet." />}
          <Button variant="secondary" onClick={() => go('/eligibility')}>Check against my profile <ArrowRight size={16} /></Button>
        </section>
      </div>
    </>
  )
}

function Eligibility() { const [schemes, setSchemes] = useState<Scholarship[]>([]); const [id, setId] = useState(''); const [result, setResult] = useState<Eligibility | null>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false); useEffect(() => { api<Scholarship[]>('/api/scholarships').then(items => { setSchemes(items); if (items[0]) setId(String(items[0].id)) }) }, []); const check = async () => { setBusy(true); try { setResult(await api<Eligibility>(`/api/eligibility/check?scheme_id=${id}`, { method: 'POST' })) } catch (err) { setError(err instanceof Error ? err.message : 'Complete your profile first.') } finally { setBusy(false) } }; return <><Title eyebrow="Eligibility checker" title="Know before you apply." text="Your result is calculated from your profile against each published rule." /><div className="checker-layout"><section className="content-section checker-form"><div className="feature-icon"><ClipboardCheck size={22} /></div><h2>Select a scheme</h2><p className="muted">We show every rule and whether your profile satisfies it.</p><label>Scholarship scheme<select value={id} onChange={e => { setId(e.target.value); setResult(null) }}>{schemes.map(s => <option value={s.id} key={s.id}>{s.name}</option>)}</select></label>{error && <div className="error-message"><CircleAlert size={16} />{error}</div>}<Button onClick={check} disabled={busy}>{busy ? 'Checking...' : 'Run eligibility check'} <ArrowRight size={17} /></Button></section><section className="content-section result-panel">{result ? <><div className={result.eligible ? 'result-heading eligible' : 'result-heading ineligible'}>{result.eligible ? <CheckCircle2 /> : <CircleAlert />}<div><span>Rule-transparent result</span><h2>{result.summary}</h2></div></div>{result.checks.map((c, i) => <div className="check-result" key={`${c.rule}-${i}`}><span className={c.passed ? 'check-icon pass' : 'check-icon fail'}>{c.passed ? <Check size={14} /> : <X size={14} />}</span><div><strong>{c.rule}</strong><small>Your profile: {String(c.actual ?? 'Not provided')} · Requirement: {c.value}</small><em className="rule-explanation">{c.explanation}</em></div></div>)}</> : <div className="result-placeholder"><ShieldCheck size={34} /><h3>Your result will appear here</h3><p>Choose a scheme and run the check to see the reasoning behind the outcome.</p></div>}</section></div></> }
function Profile({ user }: { user: User }) { const [profile, setProfile] = useState<Profile>({ category: 'ST', income: 0, age: 0, education_level: 'UG', course: 'B.Tech', percentage: 0, phone: '', state: '', district: '' }); const [saved, setSaved] = useState(false); useEffect(() => { api<Profile>('/api/students/profile').then(data => setProfile(current => ({ ...current, ...data }))) }, []); const update = (key: keyof Profile, value: string) => setProfile(p => ({ ...p, [key]: ['income', 'age', 'percentage'].includes(key) ? Number(value) : value })); const save = async (e: FormEvent) => { e.preventDefault(); await api('/api/students/profile', { method: 'POST', body: JSON.stringify(profile) }); setSaved(true); setTimeout(() => setSaved(false), 2200) }; return <><Title eyebrow="Student profile" title="Your profile, your starting point." text={`Keep these details current so ${user.full_name.split(' ')[0]} gets accurate results.`} /><form className="profile-form" onSubmit={save}><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Personal and academic</div><h2>Profile details</h2></div><UserRound size={22} /></div><div className="form-grid">{(['category', 'age', 'income', 'percentage', 'education_level', 'course', 'state', 'district', 'phone'] as (keyof Profile)[]).map(key => <label key={key}>{key === 'income' ? 'Annual family income (Rs.)' : key.replace('_', ' ')}<input type={['income', 'age', 'percentage'].includes(key) ? 'number' : 'text'} value={profile[key] || ''} onChange={e => update(key, e.target.value)} required /></label>)}</div><div className="form-actions">{saved && <span className="saved-message"><CheckCircle2 size={17} /> Profile saved</span>}<Button type="submit">Save profile</Button></div></section></form></> }
function Applications() { const [items, setItems] = useState<Application[] | null>(null); useEffect(() => { api<Application[]>('/api/applications').then(setItems) }, []); return <><Title eyebrow="My journey" title="Applications" text="Track your scholarship readiness and pre-application verification." action={<Button onClick={() => go('/discover')}>Find a scheme <ArrowRight size={17} /></Button>} />{items === null ? <Loading /> : items.length ? <div className="application-list full-list">{items.map(app => <ApplicationRow key={app.id} app={app} />)}</div> : <Empty text="No applications yet. Find a scholarship to get started." />}</> }
function ApplicationPage({ id }: { id: number }) { const [app, setApp] = useState<AppDetail | null>(null); const [scheme, setScheme] = useState<SchemeDetail | null>(null); const [file, setFile] = useState<File | null>(null); const [type, setType] = useState('caste_certificate'); const [busy, setBusy] = useState(false); const load = () => api<AppDetail>(`/api/applications/${id}`).then(data => { setApp(data); return api<SchemeDetail>(`/api/scholarships/${data.scheme_id}`) }).then(setScheme); useEffect(() => { load() }, [id]); const submit = async () => { setBusy(true); await api(`/api/applications/${id}/submit`, { method: 'POST' }); await load(); setBusy(false) }; const upload = async (e: FormEvent) => { e.preventDefault(); if (!file) return; setBusy(true); const body = new FormData(); body.append('document_type', type); body.append('file', file); await api(`/api/applications/${id}/documents`, { method: 'POST', body }); setFile(null); await load(); setBusy(false) }; if (!app || !scheme) return <Loading />; return <><button className="back-link portal-back" onClick={() => go('/applications')}><ChevronLeft size={17} /> Back to applications</button><Title eyebrow="Scholarship readiness" title={app.title} text={`Pre-application verification #${app.id}`} action={<Status value={app.status} />} /><div className="application-layout"><div className="main-column"><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Your progress</div><h2>Verification timeline</h2></div><ClipboardCheck size={22} /></div><div className="timeline">{app.timeline.map((item, i) => <div className="timeline-item" key={item.id}><span className={i === app.timeline.length - 1 ? 'timeline-dot current' : 'timeline-dot'}>{i === app.timeline.length - 1 && <Check size={12} />}</span><div><strong>{item.status}</strong><small>{new Date(item.created_at).toLocaleString('en-IN')}</small><p>{item.comment}</p></div></div>)}</div></section><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Document management</div><h2>Required documents & verification</h2></div><FileCheck2 size={22} /></div>{scheme.required_documents.map(doc => { const uploaded = app.documents.find(d => d.document_type === doc.document_type); return <div className="document-row" key={doc.id}><div className="document-label"><FileText size={18} /><span><strong>{doc.label}</strong><small>{uploaded ? uploaded.filename : 'Required before you can apply'}</small>{uploaded?.verification_summary && <em className="verification-summary">{uploaded.verification_summary}</em>}</span></div>{uploaded ? <Status value={uploaded.verification_status} /> : <span className="missing">Missing</span>}</div> })}<form className="upload-form" onSubmit={upload}><select value={type} onChange={e => setType(e.target.value)}>{scheme.required_documents.map(doc => <option value={doc.document_type} key={doc.id}>{doc.label}</option>)}</select><input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={e => setFile(e.target.files?.[0] || null)} required /><Button type="submit" disabled={busy || !file}>{busy ? 'Uploading...' : 'Upload document'}</Button></form></section></div><aside className="side-column"><section className="side-card"><div className="eyebrow">Next action</div><h3>{app.status === 'Draft' ? 'Complete pre-application verification' : app.status === 'Deficiency Raised' ? 'Action required' : 'Verification complete'}</h3><p>{app.status === 'Draft' ? 'Upload all required documents and complete the readiness check.' : app.status === 'Deficiency Raised' ? 'Resolve the detected deficiency and re-upload the affected document.' : 'Based on the information and documents provided, your scholarship readiness has been assessed. Apply on the official portal to submit the actual scholarship application.'}</p>{app.status === 'Draft' && <Button onClick={submit} disabled={busy}>Complete readiness check <ArrowRight size={16} /></Button>}{app.status !== 'Draft' && app.status !== 'Deficiency Raised' && <Button onClick={() => window.open(scheme.source_url || 'https://scholarships.gov.in/', '_blank', 'noopener,noreferrer')}>Apply on Official Portal <ArrowRight size={16} /></Button>}</section>{app.deficiencies.length > 0 && <section className="side-card deficiency-card"><div className="eyebrow">Action needed</div><h3>Mismatch / deficiency detected</h3>{app.deficiencies.map(item => <div className="deficiency" key={item.id}><strong>{item.title}</strong><p>{item.reason || item.description}</p>{item.required_action && <small className="deficiency-action">Action: {item.required_action}</small>}<Status value={item.status || 'Open'} /></div>)}</section>}</aside></div></> }
function Notifications({ items, markRead }: { items: Notification[]; markRead: (id: number) => void }) { return <><Title eyebrow="Updates" title="Notifications" text="Stay close to every change in your applications." />{items.length ? <div className="notification-list">{items.map(item => <article className={item.is_read ? 'notification-card read' : 'notification-card'} key={item.id}><span className="notification-icon"><Bell size={18} /></span><div><div className="notification-heading"><h3>{item.title}</h3><small>{new Date(item.created_at).toLocaleDateString('en-IN')}</small></div><p>{item.message}</p>{!item.is_read && <Button variant="quiet" onClick={() => markRead(item.id)}>Mark as read</Button>}</div></article>)}</div> : <Empty text="You are all caught up." />}</> }

function CreateApplication({ id }: { id: number }) {
  const [step, setStep] = useState(1)
  const [scheme, setScheme] = useState<SchemeDetail | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [eligibility, setEligibility] = useState<Eligibility | null>(null)
  const [applicationId, setApplicationId] = useState<number | null>(null)
  const [uploaded, setUploaded] = useState<DocumentItem[]>([])
  const [documentType, setDocumentType] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const selection = applicantSelection()
    const profileRequest = selection?.type === 'beneficiary' && selection.id
      ? api<Beneficiary[]>('/api/beneficiaries').then(items => items.find(item => item.id === selection.id) as Profile)
      : api<Profile>('/api/students/profile')
    Promise.all([api<SchemeDetail>(`/api/scholarships/${id}`), profileRequest])
      .then(([loadedScheme, loadedProfile]) => { setScheme(loadedScheme); setProfile(loadedProfile); setDocumentType(loadedScheme.required_documents[0]?.document_type || '') })
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load this application.'))
  }, [id])

  const ensureDraft = async () => {
    if (applicationId) return applicationId
    const selection = applicantSelection()
    const draft = await api<{ id: number }>('/api/applications', { method: 'POST', body: JSON.stringify({ scheme_id: id, applicant_type: selection?.type || 'self', beneficiary_profile_id: selection?.id, relationship_to_applicant: selection?.type === 'beneficiary' ? 'Helper' : null }) })
    setApplicationId(draft.id)
    return draft.id
  }

  const next = async () => {
    setError('')
    try {
      setBusy(true)
      if (step === 1) await ensureDraft()
      if (step === 2 && !eligibility) {
        const selection = applicantSelection()
        const result = await api<Eligibility>(`/api/eligibility/check?scheme_id=${id}${selection?.type === 'beneficiary' ? `&beneficiary_id=${selection.id}` : ''}`, { method: 'POST' })
        setEligibility(result)
      }
      setStep(current => Math.min(5, current + 1))
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to continue.') } finally { setBusy(false) }
  }

  const saveDraft = async () => { try { const draftId = await ensureDraft(); go(`/application/${draftId}`) } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save draft.') } }
  const upload = async (event: FormEvent) => {
    event.preventDefault(); if (!file || !documentType) return
    try { setBusy(true); const draftId = await ensureDraft(); const body = new FormData(); body.append('document_type', documentType); body.append('file', file); const analyzed = await api<DocumentItem>(`/api/applications/${draftId}/documents`, { method: 'POST', body }); setUploaded(current => [...current.filter(item => item.document_type !== analyzed.document_type), analyzed]); setFile(null) } catch (err) { setError(err instanceof Error ? err.message : 'Upload failed.') } finally { setBusy(false) }
  }
  const submit = async () => { try { setBusy(true); const draftId = await ensureDraft(); await api(`/api/applications/${draftId}/submit`, { method: 'POST' }); go(`/application/${draftId}`) } catch (err) { setError(err instanceof Error ? err.message : 'Unable to complete readiness check.') } finally { setBusy(false) } }

  if (!scheme || !profile) return <Loading />
  const missing = scheme.required_documents.filter(doc => !uploaded.some(item => item.document_type === doc.document_type))
  const labels = ['Student information', 'Eligibility confirmation', 'Required documents', 'Review readiness', 'Ready to apply']
  return <><button className="back-link portal-back" onClick={() => go(`/scholarship/${id}`)}><ChevronLeft size={17} /> Back to scholarship</button><Title eyebrow="Guided application" title={scheme.name} text="Save your progress as a draft at any point." /><div className="wizard-steps">{labels.map((label, index) => <div className={index + 1 === step ? 'wizard-step current' : index + 1 < step ? 'wizard-step complete' : 'wizard-step'} key={label}><span>{index + 1 < step ? <Check size={14} /> : index + 1}</span><small>{label}</small></div>)}</div>{error && <div className="error-message wizard-error"><CircleAlert size={16} />{error}</div>}<section className="content-section wizard-panel">{step === 1 && <><div className="eyebrow">Step 1</div><h2>Confirm your student information</h2><p className="muted">This information comes from your saved profile and is used by the backend eligibility engine.</p><div className="wizard-summary"><Summary label="Name" value={localStorage.getItem('scholarshipsetu_token') ? 'Authenticated student' : 'Student'} /><Summary label="Category" value={profile.category} /><Summary label="Education" value={`${profile.education_level} · ${profile.course}`} /><Summary label="Annual income" value={`Rs. ${profile.income.toLocaleString('en-IN')}`} /><Summary label="Academic score" value={`${profile.percentage}%`} /><Summary label="Location" value={`${profile.district || 'Not provided'}, ${profile.state || 'Not provided'}`} /></div></>}{step === 2 && <><div className="eyebrow">Step 2</div><h2>Confirm your eligibility</h2><p className="muted">The result below is calculated by the existing backend rule engine. The frontend does not calculate eligibility.</p>{eligibility ? <div className="wizard-result"><div className={eligibility.eligible ? 'result-heading eligible' : 'result-heading ineligible'}>{eligibility.eligible ? <CheckCircle2 /> : <CircleAlert />}<div><span>Backend result</span><h3>{eligibility.summary}</h3></div></div>{eligibility.checks.map((check, index) => <div className="check-result" key={`${check.rule}-${index}`}><span className={check.passed ? 'check-icon pass' : 'check-icon fail'}>{check.passed ? <Check size={14} /> : <X size={14} />}</span><div><strong>{check.rule}</strong><small>Profile value: {String(check.actual ?? 'Not provided')} · Requirement: {check.value}</small></div></div>)}</div> : <div className="result-placeholder"><ShieldCheck size={34} /><p>Press Continue to run the eligibility check.</p></div>}</>}{step === 3 && <><div className="eyebrow">Step 3</div><h2>Upload & verify your documents</h2><p className="muted">Scholar Bridge uses AI-assisted document analysis to check uploaded documents and surface mismatches or deficiencies.</p><div className="document-list">{scheme.required_documents.map(doc => { const item = uploaded.find(document => document.document_type === doc.document_type); return <div className="document-row" key={doc.id}><div className="document-label"><FileText size={18} /><span><strong>{doc.label}</strong><small>{item ? item.filename : doc.required ? 'Missing' : 'Optional'}</small></span></div>{item ? <Status value={item.verification_status} /> : <span className="missing">Missing</span>}</div> })}</div><form className="upload-form wizard-upload" onSubmit={upload}><select value={documentType} onChange={event => setDocumentType(event.target.value)}>{scheme.required_documents.map(doc => <option value={doc.document_type} key={doc.id}>{doc.label}</option>)}</select><input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={event => setFile(event.target.files?.[0] || null)} required /><Button type="submit" disabled={busy || !file}>{busy ? 'Uploading...' : 'Upload document'}</Button></form><p className="document-note">You can continue with missing documents and return to this draft later.</p></>}{step === 4 && <><div className="eyebrow">Step 4</div><h2>Review your scholarship readiness</h2><p className="muted">Check your eligibility and document status before completing pre-application verification.</p><div className="review-list"><Summary label="Scholarship" value={scheme.name} /><Summary label="Education level" value={scheme.level} /><Summary label="Eligibility" value={eligibility?.summary || 'Not checked'} /><Summary label="Documents" value={`${uploaded.length} uploaded · ${missing.length} missing`} /></div>{missing.length > 0 && <div className="warning-message"><CircleAlert size={17} />Complete the missing documents before you can be marked ready to apply.</div>}</>}{step === 5 && <><div className="eyebrow">Step 5</div><h2>Ready to apply</h2><p className="muted">Scholar Bridge has completed your pre-application verification. The actual scholarship application is completed on the official portal.</p><div className="submit-confirm"><ClipboardCheck size={28} /><strong>You’re ready to apply</strong><span>Based on the information and documents provided, you appear eligible to apply. Scholar Bridge does not submit the government application.</span></div><div style={{ marginTop: 18 }}><Button onClick={() => { const url = scheme.source_url || 'https://scholarships.gov.in/'; window.open(url, '_blank', 'noopener,noreferrer') }}>Apply on Official Portal <ArrowRight size={16} /></Button></div></>}</section><div className="wizard-actions"><Button variant="quiet" onClick={saveDraft}>Save as draft</Button><span>{step > 1 && <Button variant="secondary" onClick={() => setStep(current => current - 1)}><ChevronLeft size={16} /> Back</Button>}{step < 5 ? <Button onClick={next} disabled={busy || (step === 4 && missing.length > 0)}>{busy ? 'Working...' : step === 2 && !eligibility ? 'Run eligibility check' : step === 4 && missing.length > 0 ? 'Upload missing documents' : 'Continue'} <ArrowRight size={16} /></Button> : <Button onClick={submit} disabled={busy || missing.length > 0 || !eligibility?.eligible}>{busy ? 'Checking readiness...' : 'Complete verification'} <Check size={16} /></Button>}</span></div></>
}

function Summary({ label, value }: { label: string; value: string }) { return <div><small>{label}</small><strong>{value}</strong></div> }

type AdminApplication = AppDetail & { created_at: string; submitted_at?: string; student: { name: string; email: string }; profile: Profile; scheme: { id: number; name: string; benefit: string; level: string; deadline: string; description?: string }; rules: Rule[]; eligibility: Eligibility }
type AdminScheme = SchemeDetail
type AdminStats = { total_applications: number; pending_review: number; under_review: number; deficiencies: number; flagged_documents: number; automatically_verified: number; ready_for_decision: number; approved: number; rejected: number; status_distribution: Record<string, number>; applications_by_scholarship: Record<string, number> }

function AdminPortal({ user, route, logout }: { user: User; route: string; logout: () => void }) { return <div className="portal admin-portal"><header className="portal-header"><Brand /><nav className="admin-nav"><Nav href="/admin" label="Overview" icon={<Home size={17} />} active={route === '/admin'} /><Nav href="/admin/applications" label="Application queue" icon={<FileText size={17} />} active={route.startsWith('/admin/applications')} /><Nav href="/admin/schemes" label="Scholarship schemes" icon={<BookOpen size={17} />} active={route.startsWith('/admin/schemes')} /></nav><div className="user-menu"><span className="avatar">{user.full_name[0]}</span><span className="user-name">{user.full_name}</span><button className="icon-button" onClick={logout} title="Sign out"><LogOut size={17} /></button></div></header><main className="portal-main">{route === '/admin' && <AdminDashboard />} {route === '/admin/applications' && <AdminQueue />} {route.startsWith('/admin/applications/') && <AdminReview id={Number(route.split('/')[3])} />} {route === '/admin/schemes' && <AdminSchemes />} {route.startsWith('/admin/schemes/') && <AdminSchemeEditor id={Number(route.split('/')[3])} />}</main></div> }

function AdminDashboard() { const [stats, setStats] = useState<AdminStats | null>(null); const [apps, setApps] = useState<AdminApplication[]>([]); useEffect(() => { Promise.all([api<AdminStats>('/api/admin/dashboard'), api<AdminApplication[]>('/api/admin/applications')]).then(([summary, items]) => { setStats(summary); setApps(items) }) }, []); if (!stats) return <Loading />; const cards = [['Requires officer attention', stats.deficiencies + stats.flagged_documents], ['Automatically verified', stats.automatically_verified], ['Ready for decision', stats.ready_for_decision], ['Approved', stats.approved], ['Rejected', stats.rejected], ['Total applications', stats.total_applications]]; return <><Title eyebrow="Exception-first officer workspace" title="Scholarship operations" text="Clear cases move automatically. Your queue highlights only applications and documents requiring human attention." action={<Button onClick={() => go('/admin/applications')}>Open exception queue <ArrowRight size={17} /></Button>} /><div className="admin-stat-grid">{cards.map(([label, value]) => <div className="admin-stat" key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</div><div className="admin-dashboard-grid"><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Requires officer attention</div><h2>Exception queue</h2></div><a href="#/admin/applications">View queue <ArrowRight size={15} /></a></div>{apps.filter(app => app.deficiencies.some(item => item.status === 'Open') || app.documents.some(document => ['Flagged for Review', 'Mismatch Detected', 'Missing Information', 'Reupload Required'].includes(document.verification_status))).slice(0, 6).map(app => <AdminApplicationRow key={app.id} app={app} />)}{!apps.some(app => app.deficiencies.some(item => item.status === 'Open')) && <Empty text="No unresolved exceptions. Clear applications are progressing automatically." />}</section><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Distribution</div><h2>Application statuses</h2></div><ClipboardCheck size={21} /></div>{Object.entries(stats.status_distribution).map(([status, count]) => <div className="distribution-row" key={status}><span>{status}</span><strong>{count}</strong></div>)}<div className="section-heading admin-subheading"><div><div className="eyebrow">By scholarship</div><h2>Schemes</h2></div></div>{Object.entries(stats.applications_by_scholarship).map(([scheme, count]) => <div className="distribution-row" key={scheme}><span>{scheme}</span><strong>{count}</strong></div>)}</section></div></> }
function AdminApplicationRow({ app }: { app: AdminApplication }) { return <button className="admin-application-row" onClick={() => go(`/admin/applications/${app.id}`)}><span><strong>#{app.id} · {app.student.name}</strong><small>{app.scheme.name} · {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString('en-IN') : 'Not submitted'}</small></span><Status value={app.status} />{app.deficiencies.some(item => item.status === 'Open') && <span className="action-hint">Action required</span>}<ArrowRight size={17} /></button> }
function AdminQueue() { const [items, setItems] = useState<AdminApplication[]>([]); const [search, setSearch] = useState(''); const [statusFilter, setStatusFilter] = useState(''); const [schemeFilter, setSchemeFilter] = useState(''); const [schemes, setSchemes] = useState<AdminScheme[]>([]); const load = () => { const params = new URLSearchParams(); if (search) params.set('search', search); if (statusFilter) params.set('status_filter', statusFilter); if (schemeFilter) params.set('scheme_id', schemeFilter); api<AdminApplication[]>(`/api/admin/applications?${params}`).then(setItems) }; useEffect(() => { api<AdminScheme[]>('/api/admin/schemes').then(setSchemes); load() }, [statusFilter, schemeFilter]); return <><Title eyebrow="Exception-first application management" title="Officer attention queue" text="Flagged and unresolved cases appear first. AI-verified applications do not require manual document review." /><div className="queue-filters"><input placeholder="Search student name or application ID" value={search} onChange={event => setSearch(event.target.value)} /><select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">All statuses</option>{['Draft', 'Submitted', 'Under Verification', 'Ready for Decision', 'Flagged for Review', 'Deficiency Raised', 'Correction Submitted', 'Under Review', 'Approved', 'Rejected'].map(status => <option key={status}>{status}</option>)}</select><select value={schemeFilter} onChange={event => setSchemeFilter(event.target.value)}><option value="">All scholarships</option>{schemes.map(scheme => <option value={scheme.id} key={scheme.id}>{scheme.name}</option>)}</select><Button variant="secondary" onClick={load}>Search</Button></div><section className="content-section admin-table"><div className="admin-table-head"><span>Applicant</span><span>Scholarship</span><span>Status</span><span>Action</span></div>{items.map(app => <AdminApplicationRow key={app.id} app={app} />)}{!items.length && <Empty text="No applications match these filters." />}</section></> }
function AdminReview({ id }: { id: number }) { const [app, setApp] = useState<AdminApplication | null>(null); const [busy, setBusy] = useState(false); const [issue, setIssue] = useState({ field: 'Document', deficiency_type: 'Missing information', reason: '', explanation: '', required_action: '', severity: 'Medium' }); const load = () => api<AdminApplication>(`/api/admin/applications/${id}`).then(setApp); useEffect(() => { load() }, [id]); const reviewDocument = async (documentId: number, status: string) => { setBusy(true); await api(`/api/admin/documents/${documentId}/review`, { method: 'POST', body: JSON.stringify({ status, notes: status === 'Verified' ? 'Officer review passed.' : 'Correction required by officer.' }) }); await load(); setBusy(false) }; const raise = async (event: FormEvent) => { event.preventDefault(); setBusy(true); await api(`/api/admin/applications/${id}/deficiencies`, { method: 'POST', body: JSON.stringify(issue) }); await load(); setBusy(false) }; const decision = async (status: string) => { setBusy(true); try { await api(`/api/admin/applications/${id}/decision`, { method: 'POST', body: JSON.stringify({ status, comment: `Officer marked application ${status}.` }) }); await load() } catch (error) { alert(error instanceof Error ? error.message : 'Decision failed.') } finally { setBusy(false) } }; if (!app) return <Loading />; return <><button className="back-link portal-back" onClick={() => go('/admin/applications')}><ChevronLeft size={17} /> Back to queue</button><Title eyebrow={`Application #${app.id} · Officer review`} title={app.student.name} text={`${app.student.email} · ${app.scheme.name}`} action={<Status value={app.status} />} /><div className="admin-review-grid"><div className="main-column"><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Student information</div><h2>Applicant profile</h2></div><UserRound size={21} /></div><div className="review-facts"><Summary label="Category" value={app.profile.category} /><Summary label="Course" value={app.profile.course} /><Summary label="Education" value={app.profile.education_level} /><Summary label="Academic score" value={`${app.profile.percentage}%`} /><Summary label="Annual income" value={`Rs. ${app.profile.income.toLocaleString('en-IN')}`} /><Summary label="Location" value={`${app.profile.district || '-'}, ${app.profile.state || '-'}`} /></div></section><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Eligibility review</div><h2>{app.eligibility.summary}</h2></div><ShieldCheck size={21} /></div>{app.eligibility.checks.map((check, index) => <div className="check-result" key={`${check.rule}-${index}`}><span className={check.passed ? 'check-icon pass' : 'check-icon fail'}>{check.passed ? <Check size={14} /> : <X size={14} />}</span><div><strong>{check.rule}</strong><small>Expected: {check.value} · Student: {String(check.actual ?? 'Not provided')}</small><em className="rule-explanation">{check.explanation}</em></div></div>)}</section><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Document review</div><h2>Uploaded documents</h2></div><FileCheck2 size={21} /></div>{app.documents.map(document => <div className="officer-document" key={document.id}><div><strong>{document.filename}</strong><small>{document.document_type} · uploaded {new Date(document.created_at || Date.now()).toLocaleString('en-IN')}</small>{document.verification_summary && <p>{document.verification_summary}</p>}{document.extracted_data && <code>{JSON.stringify(document.extracted_data.extracted)}</code>}</div><div className="officer-document-actions"><Status value={document.verification_status} /><Button variant="secondary" onClick={() => reviewDocument(document.id, 'Verified')} disabled={busy}>Verify</Button><Button variant="quiet" onClick={() => reviewDocument(document.id, 'Reupload Required')} disabled={busy}>Request correction</Button></div></div>)}</section><section className="content-section"><div className="section-heading"><div><div className="eyebrow">Deficiency management</div><h2>Raise a deficiency</h2></div><CircleAlert size={21} /></div><form className="deficiency-form" onSubmit={raise}><input placeholder="Document or field" value={issue.field} onChange={event => setIssue({ ...issue, field: event.target.value })} required /><input placeholder="Deficiency type" value={issue.deficiency_type} onChange={event => setIssue({ ...issue, deficiency_type: event.target.value })} required /><textarea placeholder="Reason" value={issue.reason} onChange={event => setIssue({ ...issue, reason: event.target.value })} required /><textarea placeholder="Required action for student" value={issue.required_action} onChange={event => setIssue({ ...issue, required_action: event.target.value, explanation: event.target.value })} required /><Button type="submit" disabled={busy}>Raise deficiency</Button></form>{app.deficiencies.map(item => <div className="officer-deficiency" key={item.id}><strong>{item.title}</strong><span>{item.status} · {item.severity}</span><p>{item.reason || item.description}</p><small>Required action: {item.required_action || 'Review required.'}</small></div>)}</section></div><aside className="side-column"><section className="side-card"><div className="eyebrow">Officer decision</div><h3>Change application status</h3><p>Approval is blocked while high-severity deficiencies remain open.</p><div className="decision-actions"><Button variant="secondary" onClick={() => decision('Under Review')} disabled={busy}>Start review</Button><Button onClick={() => decision('Approved')} disabled={busy}>Approve</Button><Button variant="quiet" onClick={() => decision('Rejected')} disabled={busy}>Reject</Button></div></section><section className="side-card"><div className="eyebrow">Application timeline</div><div className="timeline">{app.timeline.map(item => <div className="timeline-item" key={item.id}><span className="timeline-dot current" /><div><strong>{item.status}</strong><small>{new Date(item.created_at).toLocaleString('en-IN')}</small><p>{item.comment}</p></div></div>)}</div></section></aside></div></> }
function AdminSchemes() { const [schemes, setSchemes] = useState<AdminScheme[]>([]); useEffect(() => { api<AdminScheme[]>('/api/admin/schemes').then(setSchemes) }, []); return <><Title eyebrow="Scheme management" title="Scholarship schemes" text="Manage the rules and documents used by the student eligibility engine." action={<Button onClick={() => go('/admin/schemes/new')}>Create scheme <ArrowRight size={17} /></Button>} /><div className="scheme-grid">{schemes.map(scheme => <article className="scheme-card" key={scheme.id}><span className="level-tag">{scheme.level}</span><h2>{scheme.name}</h2><p>{scheme.benefit}</p><small>{scheme.rules.length} rules · {scheme.required_documents.length} documents</small><button className="text-button" onClick={() => go(`/admin/schemes/${scheme.id}`)}>Edit scheme <ArrowRight size={15} /></button></article>)}</div></> }
function AdminSchemeEditor({ id }: { id: number }) { const [scheme, setScheme] = useState<AdminScheme | null>(null); useEffect(() => { if (id) api<AdminScheme[]>('/api/admin/schemes').then(items => setScheme(items.find(item => item.id === id) || null)); else setScheme({ id: 0, name: '', slug: '', level: 'Undergraduate', benefit: '', description: '', deadline: '2026-12-31', is_active: true, rules: [], required_documents: [] }) }, [id]); const [name, setName] = useState(''); const [level, setLevel] = useState('Undergraduate'); const [benefit, setBenefit] = useState(''); const [description, setDescription] = useState(''); const [deadline, setDeadline] = useState('2026-12-31'); const [documents, setDocuments] = useState(''); const [ruleField, setRuleField] = useState('income'); const [ruleOperator, setRuleOperator] = useState('lte'); const [ruleValue, setRuleValue] = useState('100000'); const [ruleDescription, setRuleDescription] = useState(''); const [rules, setRules] = useState<Rule[]>([]); useEffect(() => { if (scheme) { setName(scheme.name); setLevel(scheme.level); setBenefit(scheme.benefit); setDescription(scheme.description || ''); setDeadline(scheme.deadline); setDocuments(scheme.required_documents.map(item => item.document_type).join(', ')); setRules(scheme.rules) } }, [scheme]); if (!scheme) return <Loading />; const save = async (event: FormEvent) => { event.preventDefault(); const payload = { name, level, benefit, description, deadline, required_documents: documents.split(',').map(item => item.trim()).filter(Boolean), rules: rules.map(rule => ({ field: rule.field, operator: rule.operator, value: rule.value, description: rule.description })) }; if (id) await api(`/api/admin/schemes/${id}`, { method: 'PUT', body: JSON.stringify(payload) }); else { const created = await api<{ id: number }>('/api/scholarships', { method: 'POST', body: JSON.stringify(payload) }); go(`/admin/schemes/${created.id}`); return } go('/admin/schemes') }; const addRule = () => { setRules([...rules, { id: Date.now(), field: ruleField, operator: ruleOperator, value: ruleValue, description: ruleDescription || `${ruleField} ${ruleOperator} ${ruleValue}` }]); setRuleDescription('') }; return <><button className="back-link portal-back" onClick={() => go('/admin/schemes')}><ChevronLeft size={17} /> Back to schemes</button><Title eyebrow="Rule builder" title={id ? 'Edit scholarship scheme' : 'Create scholarship scheme'} text="These stored rules become the source of truth for eligibility checks." /><form className="content-section scheme-editor" onSubmit={save}><div className="form-grid"><label>Scheme name<input value={name} onChange={event => setName(event.target.value)} required /></label><label>Education level<select value={level} onChange={event => setLevel(event.target.value)}><option>Undergraduate</option><option>Post-Matric</option><option>Postgraduate</option></select></label><label>Benefit<input value={benefit} onChange={event => setBenefit(event.target.value)} required /></label><label>Deadline<input type="date" value={deadline} onChange={event => setDeadline(event.target.value)} required /></label><label>Description<input value={description} onChange={event => setDescription(event.target.value)} /></label><label>Required documents<input value={documents} onChange={event => setDocuments(event.target.value)} placeholder="caste_certificate, income_certificate" /></label></div><div className="rule-builder"><h3>Eligibility rules</h3>{rules.map(rule => <div className="rule-builder-row" key={rule.id}><span>{rule.field} {rule.operator} {rule.value}</span><button type="button" className="text-button" onClick={() => setRules(rules.filter(item => item.id !== rule.id))}>Remove</button></div>)}<div className="rule-builder-row"><select value={ruleField} onChange={event => setRuleField(event.target.value)}>{['category', 'income', 'percentage', 'education_level', 'course', 'age'].map(field => <option key={field}>{field}</option>)}</select><select value={ruleOperator} onChange={event => setRuleOperator(event.target.value)}>{['equals', 'not equals', 'gt', 'gte', 'lt', 'lte', 'in'].map(operator => <option key={operator}>{operator}</option>)}</select><input value={ruleValue} onChange={event => setRuleValue(event.target.value)} placeholder="Value" /><input value={ruleDescription} onChange={event => setRuleDescription(event.target.value)} placeholder="Explanation" /><Button variant="secondary" onClick={addRule}>Add rule</Button></div></div><Button type="submit">Save scheme <Check size={16} /></Button></form></> }

export default App
