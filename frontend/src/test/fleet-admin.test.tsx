import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { ApiClient } from '../api/client'
import type { FleetUnit, FleetUnitHistory, Page } from '../api/types'

const mocks = vi.hoisted(() => ({
  create: vi.fn(), update: vi.fn(), get: vi.fn(), start: vi.fn(), end: vi.fn(), history: vi.fn(),
}))
vi.mock('../api/fleet', () => ({
  createFleetUnit: mocks.create,
  updateFleetUnit: mocks.update,
  getFleetUnit: mocks.get,
  startMaintenance: mocks.start,
  endMaintenance: mocks.end,
  getFleetUnitHistory: mocks.history,
}))
vi.mock('../map/LocationPicker', () => ({
  LocationPicker: () => <div data-testid="location-picker" />,
}))

import { FleetUnitFormDialog, MaintenanceDialog } from '../fleet/FleetUnitDialogs'
import { FleetUnitHistoryPanel } from '../fleet/FleetUnitHistoryPanel'

const client = {} as ApiClient
const unit: FleetUnit = {
  id: 7, name: 'Alfa', license_plate: 'AAA-0001', unit_type: 'USB',
  status: 'AVAILABLE', current_location: null, capabilities: {},
  created_at: '', updated_at: '',
}

beforeEach(() => {
  Object.values(mocks).forEach(mock => mock.mockReset())
})

describe('administração da frota', () => {
  it('cadastra com payload seguro, interpreta capacidades e bloqueia envio duplicado', async () => {
    let finish!: (value: FleetUnit) => void
    mocks.create.mockReturnValue(new Promise(resolve => { finish = resolve }))
    const saved = vi.fn()
    render(<FleetUnitFormDialog client={client} unit={null} open onClose={vi.fn()} onSaved={saved} />)

    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: '  Alfa  ' } })
    fireEvent.change(screen.getByLabelText('Placa'), { target: { value: '  abc-1234  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Adicionar capacidade' }))
    fireEvent.change(screen.getByLabelText('Capacidade'), { target: { value: 'oxygen' } })
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: 'true' } })
    const submit = screen.getByRole('button', { name: 'Cadastrar unidade' })
    fireEvent.click(submit)
    fireEvent.click(submit)

    expect(mocks.create).toHaveBeenCalledOnce()
    expect(mocks.create.mock.calls[0][1]).toEqual(expect.objectContaining({
      name: 'Alfa', license_plate: 'abc-1234', unit_type: 'USB',
      current_location: null, capabilities: { oxygen: true },
    }))
    expect(mocks.create.mock.calls[0][1]).not.toHaveProperty('status')
    finish(unit)
    await waitFor(() => expect(saved).toHaveBeenCalledWith(unit, true))
  })

  it('valida capabilities no cliente e restringe tipo/capacidades fora de AVAILABLE', async () => {
    const busy = { ...unit, status: 'BUSY' as const, capabilities: { oxygen: true } }
    render(<FleetUnitFormDialog client={client} unit={busy} open onClose={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Adicionar capacidade' })).toBeDisabled()
    expect(screen.getByLabelText('Capacidade')).toBeDisabled()
  })

  it('preserva o rascunho no refresh da mesma unidade e reinicializa ao trocar ou reabrir', () => {
    const view = render(<FleetUnitFormDialog client={client} unit={unit} open onClose={vi.fn()} onSaved={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Rascunho local' } })
    fireEvent.click(screen.getByRole('button', { name: 'Adicionar capacidade' }))
    fireEvent.change(screen.getByLabelText('Capacidade'), { target: { value: 'draft' } })

    view.rerender(<FleetUnitFormDialog client={client} unit={{ ...unit, name: 'Refresh remoto' }} open onClose={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByLabelText('Nome')).toHaveValue('Rascunho local')
    expect(screen.getByLabelText('Capacidade')).toHaveValue('draft')

    const other = { ...unit, id: 8, name: 'Bravo', license_plate: 'BBB-0002' }
    view.rerender(<FleetUnitFormDialog client={client} unit={other} open onClose={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByLabelText('Nome')).toHaveValue('Bravo')
    expect(screen.queryByLabelText('Capacidade')).not.toBeInTheDocument()

    const current = { ...other, name: 'Bravo atual' }
    view.rerender(<FleetUnitFormDialog client={client} unit={current} open={false} onClose={vi.fn()} onSaved={vi.fn()} />)
    view.rerender(<FleetUnitFormDialog client={client} unit={current} open onClose={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByLabelText('Nome')).toHaveValue('Bravo atual')
  })

  it('reconcilia 409 somente após confirmação explícita e descarta o rascunho', async () => {
    const refreshed = { ...unit, name: 'Nome atual', license_plate: 'NEW-0001' }
    mocks.update.mockRejectedValue(new ApiError(409))
    mocks.get.mockResolvedValue(refreshed)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const onRefreshed = vi.fn()
    render(<FleetUnitFormDialog client={client} unit={unit} open onClose={vi.fn()} onSaved={vi.fn()} onRefreshed={onRefreshed} />)
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Meu rascunho' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('rascunho foi preservado')
    expect(screen.getByLabelText('Nome')).toHaveValue('Meu rascunho')

    const reconcile = screen.getByRole('button', { name: 'Descartar rascunho e atualizar' })
    fireEvent.click(reconcile)
    expect(mocks.get).not.toHaveBeenCalled()
    confirm.mockReturnValue(true)
    fireEvent.click(reconcile)
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(client, unit.id))
    expect(screen.getByLabelText('Nome')).toHaveValue('Nome atual')
    expect(screen.getByLabelText('Placa')).toHaveValue('NEW-0001')
    expect(onRefreshed).toHaveBeenCalledWith(refreshed)
    expect(screen.getByRole('status')).toHaveTextContent('Dados atuais carregados')
  })

  it('deduplica cliques síncronos e ignora resposta após troca de unidade', async () => {
    mocks.update.mockRejectedValue(new ApiError(409))
    let finish!: (value: FleetUnit) => void
    mocks.get.mockReturnValue(new Promise(resolve => { finish = resolve }))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const onRefreshed = vi.fn()
    const view = render(<FleetUnitFormDialog client={client} unit={unit} open onClose={vi.fn()} onSaved={vi.fn()} onRefreshed={onRefreshed} />)
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Rascunho' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    const reconcile = await screen.findByRole('button', { name: 'Descartar rascunho e atualizar' })
    fireEvent.click(reconcile)
    fireEvent.click(reconcile)
    expect(mocks.get).toHaveBeenCalledOnce()

    const other = { ...unit, id: 8, name: 'Outra unidade', license_plate: 'BBB-0002' }
    view.rerender(<FleetUnitFormDialog client={client} unit={other} open onClose={vi.fn()} onSaved={vi.fn()} onRefreshed={onRefreshed} />)
    finish({ ...unit, name: 'Resposta antiga' })
    await waitFor(() => expect(screen.getByLabelText('Nome')).toHaveValue('Outra unidade'))
    expect(onRefreshed).not.toHaveBeenCalled()
  })

  it('preserva o rascunho após erro de reconciliação e libera nova tentativa', async () => {
    mocks.update.mockRejectedValue(new ApiError(409))
    mocks.get.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ ...unit, name: 'Atualizada' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<FleetUnitFormDialog client={client} unit={unit} open onClose={vi.fn()} onSaved={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Rascunho preservado' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    const reconcile = await screen.findByRole('button', { name: 'Descartar rascunho e atualizar' })
    fireEvent.click(reconcile)
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível carregar')
    expect(screen.getByLabelText('Nome')).toHaveValue('Rascunho preservado')
    fireEvent.click(screen.getByRole('button', { name: 'Descartar rascunho e atualizar' }))
    await waitFor(() => expect(screen.getByLabelText('Nome')).toHaveValue('Atualizada'))
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })

  it('mantém o foco preso no formulário e retira o backdrop da ordem de tabulação', async () => {
    render(<FleetUnitFormDialog client={client} unit={unit} open onClose={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.getByRole('dialog', { name: 'Editar unidade' })).toBeInTheDocument()
    const title = screen.getByRole('heading', { name: 'Editar unidade' })
    await waitFor(() => expect(title).toHaveFocus())
    expect(screen.getByRole('button', { name: 'Fechar formulário' })).toHaveAttribute('tabindex', '-1')

    fireEvent.keyDown(title, { key: 'Tab', code: 'Tab', keyCode: 9 })
    expect(screen.getByRole('button', { name: 'Fechar' })).toHaveFocus()
    title.focus()
    expect(title).toHaveFocus()
    fireEvent.keyDown(title, { key: 'Tab', code: 'Tab', keyCode: 9, shiftKey: true })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Salvar alterações' })).toHaveFocus())
    fireEvent.keyDown(screen.getByRole('button', { name: 'Salvar alterações' }), { key: 'Tab', code: 'Tab', keyCode: 9 })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Fechar' })).toHaveFocus())
    const close = screen.getByRole('button', { name: 'Fechar' })
    fireEvent.keyDown(close, { key: 'Tab', code: 'Tab', keyCode: 9, shiftKey: true })
    expect(screen.getByRole('button', { name: 'Salvar alterações' })).toHaveFocus()

    const controls = screen.getByRole('dialog').querySelectorAll<HTMLElement>('button, input, select, textarea, [href]')
    controls.forEach(control => { (control as HTMLButtonElement).disabled = true })
    title.focus()
    fireEvent.keyDown(title, { key: 'Tab', code: 'Tab', keyCode: 9 })
    expect(document.activeElement).toBe(screen.getByRole('dialog'))
    expect(screen.getByRole('button', { name: 'Fechar formulário' })).not.toHaveFocus()
  })

  it('mantém a confirmação aberta no 409 e oferece reconciliação REST', async () => {
    mocks.start.mockRejectedValue(new ApiError(409))
    const refresh = vi.fn(); const saved = vi.fn()
    render(<MaintenanceDialog client={client} unit={unit} open onClose={vi.fn()} onSaved={saved} onRefresh={refresh} />)
    expect(screen.getByText(/passará de/)).toHaveTextContent('AVAILABLE')
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar alteração' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('missão incompatível')
    expect(saved).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Atualizar dados' }))
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('pagina o histórico e apresenta ator e alteração sem valores completos', async () => {
    const entry = (id: number, action: FleetUnitHistory['action']): FleetUnitHistory => ({
      id, action, previous_status: action === 'UNIT_MAINTENANCE_STARTED' ? 'AVAILABLE' : null,
      new_status: action === 'UNIT_MAINTENANCE_STARTED' ? 'MAINTENANCE' : null,
      changed_fields: action === 'UNIT_UPDATED' ? ['name'] : [], request_id: `request-${id}`,
      created_at: '2026-11-09T12:00:00Z',
      actor: { id: 1, username: 'admin', first_name: 'Ana', last_name: 'Lima' },
    })
    const first: Page<FleetUnitHistory> = { count: 2, previous: null, next: 'page-2', results: [entry(2, 'UNIT_UPDATED')] }
    const second: Page<FleetUnitHistory> = { count: 2, previous: 'page-1', next: null, results: [entry(1, 'UNIT_MAINTENANCE_STARTED')] }
    mocks.history.mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    render(<FleetUnitHistoryPanel client={client} unitId={7} version={0} />)
    expect(await screen.findByText('Dados atualizados')).toBeInTheDocument()
    expect(screen.getByText('Campos: nome')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Próxima/ }))
    expect(await screen.findByText('Entrada em manutenção')).toBeInTheDocument()
    expect(screen.getByText('AVAILABLE → MAINTENANCE')).toBeInTheDocument()
    expect(screen.getByText(/Ana Lima/)).toBeInTheDocument()
    expect(mocks.history).toHaveBeenLastCalledWith(client, 7, 2, expect.any(AbortSignal))
  })
})
