# Runbook de produção do C.O.I.N.

Este documento prepara uma futura implantação sem escolher provedor, proxy, domínio ou serviço gerenciado. Ele não substitui a documentação da infraestrutura que vier a ser adotada.

## 1. Pré-requisitos e segredos

Forneça variáveis pelo mecanismo seguro da plataforma, nunca por arquivo versionado, argumento de linha de comando ou log:

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `CHANNEL_LAYER_PREFIX`
- `ALLOWED_HOSTS`
- `WEBSOCKET_ALLOWED_ORIGINS`

Variáveis operacionais opcionais:

- `STATIC_ROOT`, com padrão `staticfiles/` no projeto;
- `DATABASE_CONNECT_TIMEOUT`, de 1 a 60 segundos, padrão 5;
- `HEALTHCHECK_TIMEOUT_MS`, de 100 a 10000 ms, padrão 2000;
- `OPENAPI_ENABLED`, desativado por padrão;
- `SECURE_SSL_REDIRECT`, desativado até a definição do proxy;
- `SECURE_HSTS_SECONDS`, inicialmente 0;
- `SECURE_HSTS_INCLUDE_SUBDOMAINS`, inicialmente falso;
- `SECURE_HSTS_PRELOAD`, inicialmente falso;
- `CSRF_TRUSTED_ORIGINS`, somente para origens HTTPS explícitas;
- `TRUST_X_FORWARDED_PROTO`, inicialmente falso.

Ative `TRUST_X_FORWARDED_PROTO` somente quando um proxy confiável remover o cabeçalho enviado pelo cliente e reconstruí-lo a partir da conexão TLS real. HTTPS e WSS são obrigatórios antes da exposição pública, mesmo quando os defaults conservadores ainda não forçam redirecionamento ou HSTS.

O proxy não pode registrar `Authorization` nem `Sec-WebSocket-Protocol`. Se a plataforma não permitir remover o segundo cabeçalho dos logs, masque qualquer valor iniciado por `coin.jwt.`.

## 2. Build e verificações

Backend:

```text
python -m pip install -r requirements.txt
python -m pip check
python manage.py check --deploy --settings=config.settings.production
python manage.py makemigrations --check --dry-run --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production
```

Enquanto TLS e proxy não forem definidos, `check --deploy` mantém visíveis
`security.W004` e `security.W008`. O schema OpenAPI atual também possui dois avisos
conhecidos de nomenclatura de enums (`UnitTypeEnum` e colisão de `status`); eles não
afetam as rotas operacionais e devem ser resolvidos junto da próxima evolução do
contrato da API. O gate do CI aceita somente essas mensagens exatas e falha para
qualquer aviso novo.

Frontend, a partir de `frontend/`:

```text
npm ci
npm run typecheck
npm test
npm run build
```

São artefatos independentes:

- `STATIC_ROOT`: assets do Django Admin e de aplicações Django;
- `frontend/dist`: SPA compilada pelo Vite.

Em uma arquitetura de mesma origem, o roteamento futuro deve usar esta precedência:

1. `/api/` para Django REST;
2. `/ws/` para ASGI com upgrade WebSocket;
3. `/admin/` para Django Admin;
4. `/static/` para `STATIC_ROOT`;
5. demais caminhos para o `index.html` da SPA.

O fallback da SPA é necessário para refresh direto em rotas como `/missions/12`. Google Fonts e `tile.openstreetmap.org` são dependências externas que uma futura CSP precisa considerar.

## 3. Release

1. Criar backup ou snapshot pré-release.
2. Validar artefatos e configurações sem imprimir segredos.
3. Executar migrations uma única vez com settings de produção.
4. Executar `collectstatic`.
5. Publicar `frontend/dist` separadamente.
6. Iniciar os workers ASGI com `DJANGO_SETTINGS_MODULE=config.settings.production`.
7. Aguardar `/health/live/` e `/health/ready/`.
8. Verificar `/health/realtime/` sem tornar a falha Redis motivo automático para retirar REST do tráfego.
9. Executar smoke tests de login, API e WebSocket.
10. Encaminhar tráfego e acompanhar logs por request ID.

Não use `runserver`. WSGI não atende WebSocket e não representa o serviço operacional completo. Migrations não devem ser iniciadas por cada worker.

No encerramento, pare novas conexões, aguarde requests e transações em andamento, encerre WebSockets e aplique um timeout de graça antes de forçar o término.

## 4. Saúde

- `/health/live/`: processo HTTP, sem banco ou Redis;
- `/health/ready/`: PostgreSQL e PostGIS, obrigatório ao domínio;
- `/health/realtime/`: channel layer, Redis em produção.

As respostas não informam host, versão, banco, usuário ou causa interna. Proteja esses caminhos contra abuso no perímetro futuro e monitore latência e frequência. Uma indisponibilidade Redis degrada notificações, mas missões confirmadas continuam persistidas no PostgreSQL.

## 5. Backup PostgreSQL/PostGIS

Defina RPO, RTO e retenção quando o serviço for escolhido. O mínimo operacional inclui backups automáticos regulares, janelas de retenção distintas, criptografia, cópia independente e restaurações ensaiadas.

Use `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` e um `PGPASSFILE` protegido ou serviço equivalente. Não coloque senha na linha de comando.

Backup lógico genérico:

```text
pg_dump --format=custom --no-owner --file=coin-AAAA-MM-DD.dump
```

Restauração inicial em banco isolado:

```text
createdb coin_restore_validation
pg_restore --no-owner --dbname=coin_restore_validation coin-AAAA-MM-DD.dump
```

Antes da restauração, confirme que PostGIS está disponível no destino. Depois:

1. conferir migrations;
2. executar verificações Django;
3. validar missões, histórico e frota;
4. validar índices e consultas geoespaciais;
5. executar testes operacionais sem dados de produção expostos;
6. registrar duração e resultado do ensaio.

Redis é transporte efêmero do Channels. Seu backup não substitui PostgreSQL. Após uma interrupção Redis, clientes recuperam o estado atual pela API REST.

## 6. Rollback

O rollback de código é possível apenas quando o schema continua compatível. Prefira migrations expand/contract: primeiro adicione estruturas compatíveis, migre o uso e só remova estruturas em release posterior.

Não execute reverse migration automaticamente. Antes de qualquer reversão, avalie perda de dados e compatibilidade da versão anterior. Restaurar backup é último recurso e pode eliminar operações posteriores ao momento do backup.

## 7. Verificação pós-release

- confirmar liveness, readiness e saúde do tempo real;
- autenticar um operador temporário autorizado;
- consultar frota e missões;
- validar uma operação controlada em ambiente apropriado;
- confirmar WebSocket sobre `wss://`;
- atualizar diretamente uma rota da SPA;
- conferir ausência de segredos em logs;
- revisar erros, latência e conexões de banco/Redis;
- registrar versão, horário, responsável e resultado.

## 8. Checklist visual manual

- login e perda de sessão;
- visão da frota e estado WebSocket;
- navegação entre visão geral e missões;
- filtros, paginação, detalhes e histórico;
- criação manual e despacho;
- coordenadas digitadas e seleção no mapa;
- refresh direto em `/missions` e `/missions/<id>`;
- teclado, foco visível e zoom de 200%;
- desktop e mobile;
- falha de tiles sem bloquear o formulário;
- estados vazio, carregando, validação, conflito e falha de rede.
