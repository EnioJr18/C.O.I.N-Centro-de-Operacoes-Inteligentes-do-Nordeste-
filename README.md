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
Crie um arquivo .env na raiz do projeto com a URL do seu banco Neon:
```bash
DEBUG=True
SECRET_KEY=sua-chave-secreta
DATABASE_URL=postgres://usuario:senha@host.neon.tech/banco?sslmode=require
```

5. Rode as migrações e inicie o servidor:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

## 🤝 Contribuição
Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou enviar pull requests.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---
Desenvolvido por **Enio Jr** para fins de estudo de Backend e portfólio 💻.

📧 Entre em contato: eniojr100@gmail.com <br>
🔗 LinkedIn: https://www.linkedin.com/in/enioeduardojr/ <br>
📷 Instagram: https://www.instagram.com/enio_juniorrr/ <br>