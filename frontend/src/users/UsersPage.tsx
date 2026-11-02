import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import {
  activateUser, createUser, deactivateUser, getUser, listUsers, updateUser, updateUserRole,
} from '../api/users'
import type { CreateUserPayload, UserFilters } from '../api/users'
import type { ManagedUser, Page, Role } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { OperationalShell } from '../layout/OperationalShell'

type Modal =
  | { kind: 'create' }
  | { kind: 'details'; user: ManagedUser }
  | { kind: 'confirm'; user: ManagedUser; action: 'role' | 'activate' | 'deactivate' }

const orderings: Array<[NonNullable<UserFilters['ordering']>, string]> = [
  ['-date_joined', 'Mais recentes'], ['date_joined', 'Mais antigos'],
  ['username', 'Username A–Z'], ['-username', 'Username Z–A'],
  ['first_name', 'Nome A–Z'], ['-first_name', 'Nome Z–A'],
]

function errorMessage(reason: unknown, fallback: string) {
  if (!(reason instanceof ApiError)) return fallback
  const detail = reason.details?.detail
  if (typeof detail === 'string') return detail
  for (const field of ['email', 'username', 'password', 'first_name', 'last_name', 'role', 'non_field_errors']) {
    const value = reason.details?.[field]
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    if (typeof value === 'string') return value
  }
  return reason.status === 409 ? 'A operação viola a proteção do último administrador ativo.' : fallback
}

function fullName(user: ManagedUser) {
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username
}

function ModalFrame({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLElement>(null)
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', close); document.body.style.overflow = 'hidden'; dialog.current?.focus()
    return () => { document.removeEventListener('keydown', close); document.body.style.overflow = previousOverflow; previousFocus?.focus() }
  }, [])
  function trapFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key !== 'Tab') return
    const focusable = [...(dialog.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), [href]') ?? [])]
    if (!focusable.length) { event.preventDefault(); return }
    const first = focusable[0]; const last = focusable.at(-1)!
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  }
  return <div className="admin-modal-layer" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <section ref={dialog} className="admin-modal" role="dialog" aria-modal="true" aria-labelledby="admin-modal-title" tabIndex={-1} onKeyDown={trapFocus}>
      <header><h2 id="admin-modal-title">{title}</h2><button type="button" className="icon-button" onClick={onClose} aria-label="Fechar diálogo">×</button></header>
      {children}
    </section>
  </div>
}

function CreateUserForm({ onClose, onCreated }: { onClose: () => void; onCreated: (user: ManagedUser) => void }) {
  const { client } = useAuth()
  const [fields, setFields] = useState<CreateUserPayload>({ username: '', email: '', first_name: '', last_name: '', password: '' })
  const [confirmation, setConfirmation] = useState('')
  const [visible, setVisible] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const sending = useRef(false)
  const change = (field: keyof CreateUserPayload, value: string) => setFields(current => ({ ...current, [field]: value }))
  async function submit(event: FormEvent) {
    event.preventDefault(); if (sending.current) return
    if (fields.password !== confirmation) { setError('A confirmação da senha inicial não confere.'); return }
    sending.current = true; setPending(true); setError('')
    try {
      const created = await createUser(client, fields)
      setFields({ username: '', email: '', first_name: '', last_name: '', password: '' }); setConfirmation('')
      onCreated(created)
    } catch (reason) { setError(errorMessage(reason, 'Não foi possível criar o usuário.')) }
    finally { sending.current = false; setPending(false) }
  }
  return <ModalFrame title="Novo usuário" onClose={onClose}><form className="admin-form" onSubmit={submit}>
    <p className="admin-guidance">A conta será criada como OPERADOR ativo. Compartilhe a senha inicial por um canal seguro; o sistema não envia e-mail automático.</p>
    <div className="admin-form-grid"><label>Nome<input value={fields.first_name} onChange={event => change('first_name', event.target.value)} /></label><label>Sobrenome<input value={fields.last_name} onChange={event => change('last_name', event.target.value)} /></label><label>Username<input required value={fields.username} onChange={event => change('username', event.target.value)} autoComplete="off" /></label><label>E-mail<input required type="email" value={fields.email} onChange={event => change('email', event.target.value)} autoComplete="off" /></label></div>
    <label>Senha inicial<span className="password-control"><input required type={visible ? 'text' : 'password'} value={fields.password} onChange={event => change('password', event.target.value)} autoComplete="new-password" /><button type="button" onClick={() => setVisible(value => !value)} aria-label={`${visible ? 'Ocultar' : 'Mostrar'} senha inicial`}>{visible ? 'Ocultar' : 'Mostrar'}</button></span></label>
    <label>Confirmar senha inicial<input required type={visible ? 'text' : 'password'} value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="new-password" /></label>
    {error && <p className="form-message" role="alert">{error}</p>}<div className="form-actions"><button type="button" className="secondary-action" onClick={onClose}>Cancelar</button><button className="primary-action" disabled={pending}>{pending ? 'Criando...' : 'Criar operador'}</button></div>
  </form></ModalFrame>
}

function UserDetails({ managed, currentId, onClose, onUpdated, onAction }: { managed: ManagedUser; currentId: number; onClose: () => void; onUpdated: (user: ManagedUser) => void; onAction: (modal: Modal) => void }) {
  const { client } = useAuth()
  const [firstName, setFirstName] = useState(managed.first_name)
  const [lastName, setLastName] = useState(managed.last_name)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const mutable = !managed.is_superuser && managed.id !== currentId
  async function submit(event: FormEvent) {
    event.preventDefault(); setPending(true); setError('')
    try { onUpdated(await updateUser(client, managed.id, { first_name: firstName, last_name: lastName })) }
    catch (reason) { setError(errorMessage(reason, 'Não foi possível atualizar o usuário.')) }
    finally { setPending(false) }
  }
  return <ModalFrame title="Detalhes do usuário" onClose={onClose}><form className="admin-form" onSubmit={submit}>
    <div className="identity-summary"><strong>{fullName(managed)}</strong><span>@{managed.username}</span>{managed.is_superuser && <b>SUPERUSUÁRIO</b>}</div>
    <div className="admin-form-grid"><label>Nome<input disabled={!mutable} value={firstName} onChange={event => setFirstName(event.target.value)} /></label><label>Sobrenome<input disabled={!mutable} value={lastName} onChange={event => setLastName(event.target.value)} /></label></div>
    <div className="readonly-grid"><div><span>E-mail</span><strong>{managed.email}</strong><small>Somente leitura</small></div><div><span>Username</span><strong>{managed.username}</strong><small>Somente leitura</small></div><div><span>Papel</span><strong>{managed.role ?? 'Sem perfil'}</strong><small>{managed.is_active ? 'Conta ativa' : 'Conta inativa'}</small></div></div>
    {!mutable && <p className="admin-guidance">{managed.is_superuser ? 'Superusuários são somente leitura nesta área.' : 'Use a página de perfil para alterar sua própria conta.'}</p>}
    {error && <p className="form-message" role="alert">{error}</p>}<div className="form-actions">{mutable && <><button type="button" className="secondary-action" onClick={() => onAction({ kind: 'confirm', user: managed, action: 'role' })}>{managed.role === 'ADMIN' ? 'Rebaixar para OPERADOR' : 'Promover para ADMIN'}</button><button type="button" className="secondary-action" onClick={() => onAction({ kind: 'confirm', user: managed, action: managed.is_active ? 'deactivate' : 'activate' })}>{managed.is_active ? 'Desativar conta' : 'Ativar conta'}</button><button className="primary-action" disabled={pending}>{pending ? 'Salvando...' : 'Salvar nomes'}</button></>}<button type="button" className="secondary-action" onClick={onClose}>Fechar</button></div>
  </form></ModalFrame>
}

function Confirmation({ modal, onClose, onConfirm, pending, error }: { modal: Extract<Modal, { kind: 'confirm' }>; onClose: () => void; onConfirm: () => void; pending: boolean; error: string }) {
  const nextRole: Role = modal.user.role === 'ADMIN' ? 'OPERADOR' : 'ADMIN'
  const text = modal.action === 'role'
    ? `Alterar ${fullName(modal.user)} de ${modal.user.role ?? 'sem perfil'} para ${nextRole}? A permissão operacional será atualizada imediatamente.`
    : `${modal.action === 'deactivate' ? 'Desativar' : 'Ativar'} a conta de ${fullName(modal.user)}? ${modal.action === 'deactivate' ? 'O acesso será bloqueado enquanto a conta estiver inativa.' : 'O usuário poderá voltar a autenticar.'}`
  return <ModalFrame title="Confirmar operação" onClose={onClose}><p className="confirmation-copy">{text}</p>{error && <p className="form-message" role="alert">{error}</p>}<div className="form-actions"><button className="secondary-action" onClick={onClose}>Cancelar</button><button className={`primary-action${modal.action === 'deactivate' ? ' danger-action' : ''}`} disabled={pending} onClick={onConfirm}>{pending ? 'Processando...' : 'Confirmar'}</button></div></ModalFrame>
}

export function UsersPage() {
  const { client, user: currentUser } = useAuth()
  const [params, setParams] = useSearchParams()
  const query = params.toString()
  const page = Math.max(1, Number(params.get('page')) || 1)
  const [search, setSearch] = useState(params.get('search') ?? '')
  const [role, setRole] = useState(params.get('role') ?? '')
  const [active, setActive] = useState(params.get('is_active') ?? '')
  const [ordering, setOrdering] = useState(params.get('ordering') ?? '-date_joined')
  const [data, setData] = useState<Page<ManagedUser> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [modal, setModal] = useState<Modal | null>(null)
  const [actionPending, setActionPending] = useState(false)
  const [actionError, setActionError] = useState('')
  const sequence = useRef(0)

  const filters = useMemo<UserFilters>(() => ({
    page,
    search: params.get('search') || undefined,
    role: (params.get('role') || undefined) as UserFilters['role'],
    isActive: params.has('is_active') ? params.get('is_active') === 'true' : undefined,
    ordering: (params.get('ordering') || '-date_joined') as UserFilters['ordering'],
  }), [page, query])

  useEffect(() => { setSearch(params.get('search') ?? ''); setRole(params.get('role') ?? ''); setActive(params.get('is_active') ?? ''); setOrdering(params.get('ordering') ?? '-date_joined') }, [query])

  const load = useCallback(async (signal?: AbortSignal) => {
    const current = ++sequence.current; setLoading(true)
    try { const result = await listUsers(client, filters, signal); if (current === sequence.current && !signal?.aborted) { setData(result); setError('') } }
    catch (reason) { if (current === sequence.current && !signal?.aborted) setError(errorMessage(reason, 'Não foi possível carregar os usuários.')) }
    finally { if (current === sequence.current && !signal?.aborted) setLoading(false) }
  }, [client, filters])
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => { controller.abort(); sequence.current++ } }, [load])

  function applyFilters(event: FormEvent) {
    event.preventDefault(); const next = new URLSearchParams()
    if (search.trim()) next.set('search', search.trim())
    if (role) next.set('role', role)
    if (active) next.set('is_active', active)
    if (ordering && ordering !== '-date_joined') next.set('ordering', ordering)
    setParams(next)
  }
  function setPage(value: number) { const next = new URLSearchParams(params); value > 1 ? next.set('page', String(value)) : next.delete('page'); setParams(next) }
  async function openDetails(id: number) {
    setError('')
    try { setModal({ kind: 'details', user: await getUser(client, id) }) }
    catch (reason) { setError(errorMessage(reason, 'Não foi possível consultar o usuário.')) }
  }
  async function confirmAction() {
    if (!modal || modal.kind !== 'confirm') return
    setActionPending(true); setActionError('')
    try {
      const updated = modal.action === 'role'
        ? await updateUserRole(client, modal.user.id, modal.user.role === 'ADMIN' ? 'OPERADOR' : 'ADMIN')
        : modal.action === 'activate' ? await activateUser(client, modal.user.id) : await deactivateUser(client, modal.user.id)
      setModal(null); setSuccess(`Usuário ${fullName(updated)} atualizado com sucesso.`); await load()
    } catch (reason) { setActionError(errorMessage(reason, 'Não foi possível concluir a operação.')) }
    finally { setActionPending(false) }
  }
  return <OperationalShell section="USUÁRIOS"><main id="main-content" className="content users-content" tabIndex={-1}>
    <div className="page-heading"><div><p className="eyebrow">ADMINISTRAÇÃO <span> / </span> USUÁRIOS</p><h1>Gerenciamento de usuários<span>.</span></h1><p>Cadastre operadores, consulte contas e administre papéis e acessos com segurança.</p></div><button className="primary-action" onClick={() => { setSuccess(''); setModal({ kind: 'create' }) }}>Novo usuário</button></div>
    <form className="user-filters" onSubmit={applyFilters}><label>Busca<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Nome, e-mail ou username" /></label><label>Papel<select value={role} onChange={event => setRole(event.target.value)}><option value="">Todos</option><option value="ADMIN">ADMIN</option><option value="OPERADOR">OPERADOR</option></select></label><label>Situação<select value={active} onChange={event => setActive(event.target.value)}><option value="">Todas</option><option value="true">Ativos</option><option value="false">Inativos</option></select></label><label>Ordenação<select value={ordering} onChange={event => setOrdering(event.target.value)}>{orderings.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button className="filter-button">Aplicar filtros</button></form>
    {success && <div className="success-message" role="status">{success}</div>}{error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => void load()}>Tentar novamente ↻</button></div>}
    <section className="users-panel" aria-label="Lista de usuários">{loading && <div className="empty-state" role="status">Carregando usuários...</div>}{!loading && !error && data?.results.length === 0 && <div className="empty-state"><strong>{params.has('search') || params.has('role') || params.has('is_active') ? 'Nenhum resultado encontrado.' : 'Nenhum usuário cadastrado.'}</strong><span>Ajuste os filtros ou cadastre um novo operador.</span></div>}
      {!loading && data && data.results.length > 0 && <div className="users-table-wrap"><table className="users-table"><thead><tr><th>Usuário</th><th>E-mail</th><th>Papel</th><th>Situação</th><th>Criação</th><th><span className="sr-only">Ações</span></th></tr></thead><tbody>{data.results.map(managed => <tr key={managed.id}><td><strong>{fullName(managed)}</strong><small>@{managed.username}</small>{managed.is_superuser && <b className="super-badge">SUPERUSUÁRIO</b>}</td><td>{managed.email}</td><td><span className={`role-badge role-${managed.role?.toLowerCase() ?? 'none'}`}>{managed.role ?? 'Sem perfil'}</span></td><td><span className={`account-status ${managed.is_active ? 'account-active' : 'account-inactive'}`}>{managed.is_active ? 'Ativo' : 'Inativo'}</span></td><td>{new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' }).format(new Date(managed.date_joined))}</td><td><button className="table-action" onClick={() => void openDetails(managed.id)}>Ver detalhes</button></td></tr>)}</tbody></table></div>}
      {!loading && data && data.count > 0 && <div className="pagination"><button disabled={!data.previous || page === 1} onClick={() => setPage(page - 1)}>← Anterior</button><span>Página {page} de {Math.max(1, Math.ceil(data.count / 20))} · {data.count} usuários</span><button disabled={!data.next} onClick={() => setPage(page + 1)}>Próxima →</button></div>}
    </section><footer className="app-footer"><span>C.O.I.N. <b> / </b> CENTRO DE OPERAÇÕES INTELIGENTES</span><span>ADMINISTRAÇÃO DE USUÁRIOS</span></footer>
    {modal?.kind === 'create' && <CreateUserForm onClose={() => setModal(null)} onCreated={created => { setModal(null); setSuccess(`Operador ${fullName(created)} criado com sucesso.`); void load() }} />}
    {modal?.kind === 'details' && <UserDetails managed={modal.user} currentId={currentUser!.id} onClose={() => setModal(null)} onUpdated={updated => { setModal({ kind: 'details', user: updated }); setSuccess('Dados do usuário atualizados com sucesso.'); void load() }} onAction={next => { setActionError(''); setModal(next) }} />}
    {modal?.kind === 'confirm' && <Confirmation modal={modal} onClose={() => setModal(null)} onConfirm={() => void confirmAction()} pending={actionPending} error={actionError} />}
  </main></OperationalShell>
}
