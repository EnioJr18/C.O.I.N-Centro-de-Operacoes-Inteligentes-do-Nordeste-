import { Link } from 'react-router-dom'
import { OperationalShell } from '../layout/OperationalShell'
import { Icon } from '../layout/Icon'

type ReservedKind = 'ALERTAS'

const content: Record<ReservedKind, { icon: 'alerts' | 'users' | 'profile'; title: string; description: string; note: string }> = {
  ALERTAS: { icon: 'alerts', title: 'Central de alertas', description: 'Este módulo reunirá alertas operacionais persistentes em uma sprint futura.', note: 'Nenhuma notificação fictícia é exibida nesta área.' },
}

export function ReservedPage({ kind }: { kind: ReservedKind }) {
  const item = content[kind]
  return <OperationalShell section={kind}><main id="main-content" className="content reserved-content" tabIndex={-1}><section className="reserved-panel"><span className="reserved-icon"><Icon name={item.icon} /></span><p className="eyebrow">MÓDULO EM PREPARAÇÃO</p><h1>{item.title}<span>.</span></h1><p>{item.description}</p><div className="reserved-note">{item.note}</div><Link className="primary-action" to="/">Voltar à visão geral</Link></section></main></OperationalShell>
}
