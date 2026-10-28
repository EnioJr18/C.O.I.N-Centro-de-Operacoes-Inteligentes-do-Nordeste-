# C.O.I.N. - Centro de Operações Inteligentes do Nordeste 🚑📍

O **C.O.I.N.** é um motor de despacho geoespacial de alta concorrência construído para otimizar o tempo de resposta e o roteamento de unidades móveis de urgência. 

Este projeto eleva propostas de pesquisa de rastreamento de frotas e ferramentas digitais de saúde a um nível de engenharia de software de produção, focando em lidar com os maiores desafios de sistemas críticos: **concorrência de dados, precisão espacial e auditoria imutável.**

## 🎯 O Problema que Resolvemos
Em operações de emergência, frações de segundo salvam vidas. Sistemas de despacho tradicionais falham ao enfrentar alta concorrência (duas ocorrências tentando puxar a mesma viatura) e cálculos de distância imprecisos. O C.O.I.N. resolve isso aplicando travas de banco de dados nativas e cálculos geoespaciais sobre esferoides.

## 🚀 Diferenciais Técnicos (Engineering Highlights)

* **Geo-Routing com PostGIS (Geography):** Utilização de campos `PointField(geography=True)` para cálculos matematicamente precisos da curvatura da terra na vasta região do Nordeste, filtrando as viaturas mais próximas em milissegundos usando `ST_Distance`.
* **Prevenção de Race Conditions:** Implementação de `select_for_update()` atrelado a blocos `transaction.atomic()` do Django para garantir Locks a nível de linha (Row-Level Locking) no PostgreSQL. Impede o duplo despacho da mesma ambulância no mesmo milissegundo.
* **Filtros de Alta Performance (JSONB):** Uso do tipo JSONB com índices GIN no PostgreSQL (via Neon) para classificar viaturas por equipamentos (ex: UTI móvel, desfibrilador) sem a necessidade de JOINs pesados em tabelas auxiliares.
* **Auditoria Imutável (Event-Driven):** Padrão *Observer* implementado via **Django Signals** (`pre_save` e `post_save`). O sistema possui uma tabela de histórico *Append-Only* que escuta mudanças de estado da missão e gera logs de auditoria automaticamente, garantindo o desacoplamento das regras de negócio.

## 🏗️ Arquitetura (Inspirada em DDD)

O projeto foge do padrão MVC acoplado e adota uma separação rigorosa de responsabilidades:

* **Controllers:** Recebem a carga HTTP, validam o payload e delegam a ação.
* **Services:** Concentram as lógicas de *Escrita* e transações de banco (Mudança de Estado).
* **Selectors:** Concentram as lógicas de *Leitura* e queries complexas de PostGIS.
* **Models:** Entidades ricas e regras de dados.

## 🛠️ Stack Tecnológica
* **Backend:** Python 3, Django, Django REST Framework
* **Banco de Dados:** PostgreSQL hospedado na [Neon](https://neon.tech/)
* **Extensão Espacial:** PostGIS (GDAL/GEOS)

## ⚙️ Como rodar localmente

1. Clone o repositório:
```bash
git clone https://github.com/EnioJr18/C.O.I.N-Centro-de-Opera-es-Inteligentes-do-Nordeste-.git
cd coin-dispatch
```

2. Crie e ative o ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
Copie `.env.example` para `.env` e ajuste os valores locais. O arquivo `.env` não é versionado. Redis é opcional no desenvolvimento; deixe `REDIS_URL` vazia para usar a camada em memória:
```bash
DEBUG=True
SECRET_KEY=sua-chave-secreta
DATABASE_URL=postgresql://usuario:senha@host/banco
ALLOWED_HOSTS=localhost,127.0.0.1
WEBSOCKET_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
REDIS_URL=
CHANNEL_LAYER_PREFIX=coin-local
```

5. Rode as migrações e inicie o servidor:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

### Configurações por ambiente

- `config.settings.base`: configuração comum e camada de canais em memória, sem carregar `.env` automaticamente.
- `config.settings.local`: usada por padrão pelo `manage.py`; carrega o `.env` local preservando a precedência das variáveis do processo. Se `REDIS_URL` estiver preenchida, usa `channels_redis.core.RedisChannelLayer`; caso contrário, mantém a memória.
- `config.settings.test`: carrega o `.env` apenas para facilitar o banco local, mas sempre força `InMemoryChannelLayer`, mesmo que `REDIS_URL` exista.
- `config.settings.production`: nunca carrega `.env`; exige configuração segura pelo ambiente, Redis e prefixo explícitos, e não possui fallback para memória.

Para iniciar o ASGI local, informe explicitamente as settings locais:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"
daphne config.asgi:application
```

Em Linux ou macOS, use `DJANGO_SETTINGS_MODULE=config.settings.local daphne config.asgi:application`. A suíte normal deve ser executada com `python manage.py test --settings=config.settings.test` e não requer Redis real.

Para testar Redis localmente, configure uma `REDIS_URL` válida e mantenha o mesmo `CHANNEL_LAYER_PREFIX` em todos os processos HTTP e ASGI. Use um prefixo diferente para cada ambiente. O navegador continua acessando apenas HTTP e WebSocket; ele nunca se conecta diretamente ao Redis.

Em produção, execute o ASGI com `DJANGO_SETTINGS_MODULE=config.settings.production`. São obrigatórios `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `WEBSOCKET_ALLOWED_ORIGINS`, `REDIS_URL` e `CHANNEL_LAYER_PREFIX`. A origem WebSocket deve ser HTTPS e o acesso do navegador deve usar `wss://`. Quando Redis estiver fora de uma rede privada confiável, use `rediss://` conforme o serviço escolhido. HTTPS, HSTS, redirecionamento e cabeçalhos de proxy devem ser configurados somente depois de validar a infraestrutura real; um proxy confiável deve remover e reconstruir seus próprios cabeçalhos e não deve registrar `Authorization` ou `Sec-WebSocket-Protocol`.

O CI mantém os testes Django em memória e executa, em um job separado, um smoke test com Redis temporário. Esse teste registra um canal em um processo e publica pelo mesmo grupo em outro processo, comprovando que a camada é compartilhada sem depender de PostgreSQL ou Neon.

## Frontend operacional

O diretório `frontend/` contém React, TypeScript, Vite, Tailwind CSS e Leaflet. Requer Node.js 24 e npm. Na pasta `frontend`, execute `npm ci` e depois `npm run dev`. O servidor usa `http://localhost:5173` com porta fixa.

O Vite encaminha `/api/` e `/ws/` ao backend local. Para alterar o destino, copie `frontend/.env.example` para `frontend/.env.local` e ajuste `COIN_BACKEND_ORIGIN`; não coloque credenciais nesse arquivo. No backend, configure `WEBSOCKET_ALLOWED_ORIGINS` com a origem exata usada no navegador (por exemplo, `http://localhost:5173`), e inicie o servidor ASGI. Em produção, configure um proxy para a API e para o upgrade WebSocket, mantendo a validação de origem; não use o servidor Vite de desenvolvimento como implantação.

Verificações do frontend: `npm run typecheck`, `npm test` e `npm run build`. Os testes simulam rede e não precisam de Neon, Redis ou tiles. Para integração manual, utilize um PostgreSQL/PostGIS local isolado, aplique as migrations apenas nesse banco, crie um operador temporário e inicie o backend ASGI; entre com esse operador no frontend, confira a frota e dispare uma emergência pela API a partir de outro cliente autorizado. Nunca use dados de produção para esse teste.

Os tokens ficam somente em memória: atualizar ou fechar a página exige novo login. O botão Sair limpa a sessão local, mas não revoga o refresh token no servidor. O mapa usa tiles públicos do OpenStreetMap com atribuição; o serviço é limitado e sem garantia de disponibilidade, por isso uma operação em escala precisa avaliar outro provedor ou infraestrutura própria. A localização exibida vem da API; não há rastreamento GPS ao vivo nem telas de cadastro, conclusão ou cancelamento de missões nesta versão.

## WebSocket de atualizações da frota

Configure `WEBSOCKET_ALLOWED_ORIGINS` como uma lista separada por vírgulas de origens HTTP(S) exatas, incluindo a porta quando necessária. O padrão é vazio e recusa todas as origens; em produção configure apenas as origens autorizadas. O exemplo local está em `.env.example`. Origens ausentes são recusadas.

Um cliente autenticado oferece os subprotocolos, nesta ordem, `coin.v1` e `coin.jwt.<access-token>` ao conectar em `/ws/fleet/`. O servidor negocia somente `coin.v1`. Não coloque o token na URL nem registre os subprotocolos em logs de proxy ou aplicação. Use `wss://` em produção. Somente usuários ativos com papel OPERADOR ou ADMIN, ou superusuários ativos, recebem eventos. A conexão estabelecida fecha com código `4401` quando o token expira e `4403` quando a autorização é revogada. Na recusa durante o handshake, navegadores podem não expor esses códigos.

O evento de despacho mantém `action`, `unit_id`, `unit_name`, `new_status`, `mission_id`, `lat` e `lon`, e acrescenta `event_id` (UUID), `schema_version` (inteiro, atualmente 1) e `occurred_at` (data UTC ISO 8601). Exemplo:

```json
{"event_id":"c6127b0a-99fb-48ad-a625-d978e33f9fa3","schema_version":1,"occurred_at":"2026-10-27T12:30:00+00:00","action":"DISPATCH","unit_id":1,"unit_name":"Alfa 01","new_status":"BUSY","mission_id":42,"lat":-9.0,"lon":-35.0}
```

A publicação ocorre após o commit e é uma notificação em tempo real sem garantia de entrega, persistência ou replay. Após reconectar, o cliente reconcilia seu estado consultando a API HTTP. A camada em memória é limitada a um processo e não deve ser usada em produção; todos os workers de produção precisam compartilhar o mesmo Redis e o mesmo prefixo.

## 🤝 Contribuição
Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou enviar pull requests.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---
Desenvolvido por **Enio Jr** para fins de estudo de Backend e portfólio 💻.

📧 Entre em contato: eniojr100@gmail.com <br>
🔗 LinkedIn: https://www.linkedin.com/in/enioeduardojr/ <br>
📷 Instagram: https://www.instagram.com/enio_juniorrr/ <br>
