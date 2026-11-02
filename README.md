# CoreGestor

Sistema web para assistência técnica de computadores, notebooks e celulares, implementado a partir de `SOLICITACAO_SISTEMA_ASSISTENCIA.md`.

## Executar no Windows

Requer Python 3.12 ou superior. Execute nesta pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py demo
python manage.py runserver 127.0.0.1:8000
```

Abra **http://127.0.0.1:8000/**. O comando `demo` gera catálogo, seis atendimentos fictícios e os usuários `admin_demo` e `tecnico_demo`. As senhas são aleatórias e aparecem no terminal somente na criação. Executá-lo novamente não altera senhas nem duplica o catálogo. Para trocar uma senha: `python manage.py changepassword admin_demo`.

Para uma instalação sem dados fictícios, não execute `demo`: use `python manage.py createsuperuser` e cadastre a identidade da assistência e os serviços em `/gestao/`.

## Acessos e operação

| Endereço | Uso |
| --- | --- |
| `/` | Catálogo público e contato por serviço |
| `/solicitar/` | Formulário em três etapas, protocolo e acompanhamento |
| `/entrar/` | Autenticação de funcionários |
| `/painel/` | Indicadores, busca, filtros, paginação e OS |
| `/painel/solicitacoes/` | Análise e conversão de pedidos em OS |
| `/painel/nova-os/` | Entrada direta de equipamento no balcão |
| `/gestao/` | Cadastro de serviços, equipe e identidade |

No cadastro de funcionários do Django, **superusuário** representa administrador; usuário ativo comum representa técnico. Marque também **membro da equipe** para o administrador entrar em `/gestao/`. Técnicos entram no painel operacional e só acessam suas OS. Não conceda superusuário a técnicos. Desative usuários e serviços em vez de excluí-los; a exclusão não é disponibilizada pela interface.

Em configurações da assistência, informe WhatsApp com código do país e DDD, somente números. O número inicial é ilustrativo: substitua antes de atender clientes. Somente uma configuração é utilizada por instalação. O fuso inicial é `America/Sao_Paulo` e pode ser alterado em `coregestor/settings.py`.

O cliente recebe um link pessoal sem criar senha. O administrador pode revogar o link anterior, gerando outro no detalhe da solicitação ou da OS. O token é independente do protocolo sequencial. Não há API pública que serialize os modelos: a página pública recebe uma projeção de campos permitidos e somente eventos e anexos liberados.

Solicitações não geram OS automaticamente. No recebimento, confira defeito, conservação, acessórios, identificação e técnico. Para reparo, registre diagnóstico, orçamento e aprovação recebida por telefone, WhatsApp ou presencialmente. O orçamento é informado por linhas no formato `descrição; quantidade; valor unitário`. Os totais usam `Decimal`; cada alteração gera uma versão preservando a decisão anterior e bloqueia a continuação até nova aprovação.

Notas são internas por padrão. Uma mudança de status registra autor, data e estados anterior e novo na mesma transação. Para corrigir um registro, crie uma atualização e informe o ID do evento corrigido; o original permanece no histórico. Reabertura exige administrador, status “Em diagnóstico” e justificativa. Cancelamento exige motivo e destinação do equipamento. Finalização exige administrador e confirmação de entrega.

## Arquitetura e dados

Django com templates HTML, CSS e JavaScript pequenos, sem framework de frontend. SQLite torna a instalação local simples. Autenticação, hash de senhas, sessões, CSRF, formulários e migrações são nativos do Django. A estrutura usa as [transações do Django](https://docs.djangoproject.com/en/5.2/topics/db/transactions/) para gravar alterações e histórico em conjunto.

- `assistencia/models.py`: objetos do domínio e regras de transição/autorizações.
- `assistencia/services.py`: operações transacionais, recebimento, versões de orçamento e histórico.
- `assistencia/forms.py`: validação de entrada, dinheiro e uploads.
- `assistencia/views.py`: autorização de acesso e coordenação HTTP.
- `assistencia/templates/` e `assistencia/static/`: interface responsiva, navegação e formulários.
- `assistencia/migrations/`: modelo relacional versionado.

Relacionamentos: Cliente → Equipamento; Solicitação → Cliente + Equipamento + Serviço; OS → Solicitação (única) + Técnico; OS → versões de Orçamento → Itens; OS → Atividades → Anexos. Anexos de solicitação também podem existir antes da OS. Funcionários usam o usuário nativo do Django. Referências são protegidas contra exclusão.

O SQLite usa transações `IMMEDIATE` e tempo limite de 20 segundos, serializando gravações concorrentes; a restrição `OneToOne` impede OS duplicadas. Chaves de idempotência evitam repetição de pedidos, atualizações e operações de orçamento. Atualizações de status usam também uma versão para detectar formulários desatualizados. SQLite é adequado a uma assistência de baixo volume; cargas com muita gravação simultânea exigirão migração de banco e revisão das opções específicas de SQLite.

Uploads aceitam JPEG, PNG e WebP de até 5 MB, com verificação do conteúdo pelo Pillow, limite de 25 megapixels e nome de armazenamento aleatório. Downloads são forçados e protegidos por autorização; o diretório privado nunca deve ser servido diretamente pelo servidor web. Senhas de aparelhos e credenciais pessoais não são solicitadas.

## Validação automática

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
node --check assistencia/static/assistencia/app.js
```

Os testes cobrem fluxo até entrega/reabertura, recusa, nova aprovação após alteração, dinheiro decimal, autorização por objeto, sigilo público, revogação, CSRF, correções, idempotência e restrição de unicidade.

Também há um smoke test opcional no Chrome instalado no Windows, que cria e remove seus próprios dados temporários. Com o servidor rodando em outro terminal: `python -m pip install playwright` e `python scripts/qa_browser.py`. Ele percorre o fluxo completo e captura catálogo/painel em desktop e celular na pasta temporária do Windows. Playwright é apenas ferramenta de desenvolvimento, sem dependência em produção.

## Validação manual

1. No catálogo, selecione um serviço e confira se ele permanece selecionado. Preencha contato, equipamento e problema; revise e envie. Guarde o link recebido.
2. Entre como administrador, abra Solicitações e confira que não foi criada OS automaticamente. Altere a situação e confirme o recebimento com acessórios, conservação e foto.
3. Confira o vínculo único e o evento de entrada. Busque por cliente, equipamento e número; combine filtros de técnico, período, atraso e status.
4. Como técnico atribuído, registre diagnóstico, orçamento e uma nota interna sem mudar o status. Tente acessar uma OS de outro técnico; o acesso deve ser negado.
5. Vá a “Aguardando aprovação” e tente executar sem aprovação; o sistema deve bloquear. Como administrador, registre a decisão com canal e observação.
6. Execute, aguarde peça, volte à execução, realize testes e marque pronto. Altere o orçamento depois de aprovado: uma nova decisão será necessária. Teste também a recusa e retirada sem reparo.
7. No link público, confirme que notas internas, contatos pessoais e anexos privados não aparecem. Revogue o link e confira que o antigo retorna 404.
8. Finalize com administrador e confirmação de entrega. Tente editar a OS encerrada; reabra com justificativa e confira a preservação do histórico.
9. Repita com largura de 390 px e somente teclado: Tab, Shift+Tab, Enter e Espaço. Confira foco, rótulos, mensagens, resumo e confirmações. Sem JavaScript, todos os campos do pedido continuam disponíveis.
10. Reinicie o servidor e confira que os atendimentos persistem. Restaure um backup em uma cópia da instalação e confira banco e anexos.

## Backup e restauração

Pause o atendimento e uploads durante o backup para manter banco e arquivos sincronizados:

```powershell
python manage.py backup C:\Backups\CoreGestor-2026-10-29
```

Escolha sempre uma pasta nova. O comando usa a API de backup do SQLite e copia os anexos. Guarde o backup com controle de acesso, pois contém dados pessoais e tokens. Guarde `DJANGO_SECRET_KEY` ou `.secret_key` separadamente e mantenha retenção de backups em local protegido.

Para restaurar: pare o servidor; faça backup da instalação atual; copie `db.sqlite3` e `private_uploads` do backup para a raiz da instalação, substituindo os correspondentes; restaure a mesma chave secreta; instale as dependências; execute `python manage.py migrate` e reinicie. Valide um atendimento e um anexo. Restaurar uma chave diferente encerra as sessões de funcionários.

## Configuração para publicação

Esta entrega é local e não publica dados em serviços externos. Antes de hospedar, configure as variáveis de ambiente:

```powershell
$env:DJANGO_DEBUG = '0'
$env:DJANGO_ALLOWED_HOSTS = 'assistencia.seudominio.com'
$env:DJANGO_SECRET_KEY = '<segredo aleatório exclusivo da instalação>'
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Use HTTPS e um servidor WSGI/ASGI apropriado; `runserver` é de desenvolvimento. Sirva apenas `staticfiles`, mantenha `private_uploads` privado, desative logs de acesso para URLs de acompanhamento (contêm tokens), configure limites de requisição no proxy, credenciais próprias e backup recorrente. Cookies seguros, redirecionamento HTTPS e HSTS são ativados quando `DJANGO_DEBUG=0`. Configure `SECURE_PROXY_SSL_HEADER` apenas se houver um proxy confiável que remova cabeçalhos externos.

Não estão incluídos os itens excluídos da especificação: estoque completo, fiscal, contabilidade, pagamentos, marketplace, chatbot e aprovação online pelo cliente.
