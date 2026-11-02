# Solicitação de desenvolvimento — Sistema para assistência técnica

## 1. Objetivo

Desenvolva uma aplicação web para assistências técnicas de computadores, notebooks e celulares. O sistema deve integrar um catálogo público de serviços, o recebimento de solicitações e um painel administrativo de ordens de serviço (OS).

Utilize programação orientada a objetos no domínio e nas regras de negócio, uma arquitetura simples e uma interface minimalista. Aplique o conceito de affordance para que o usuário perceba quais ações estão disponíveis e como executá-las.

Este documento é uma especificação para implementação. Entregue um sistema funcional, com persistência de dados e fluxos completos, conforme os critérios de aceite.

## 2. Escopo da primeira versão

- Uma assistência por instalação, com identidade e contatos configuráveis.
- Catálogo público de serviços.
- Formulário de solicitação e cadastro de cliente e equipamento.
- Análise das solicitações no painel administrativo.
- Conversão de solicitação em OS após o recebimento do equipamento.
- Tabela de OS, filtros e página de detalhes em formato de card.
- Diagnóstico, orçamento e registro de aprovação ou recusa.
- Histórico de atividades, comentários e anexos.
- Acompanhamento pelo cliente por link individual.
- Autenticação de funcionários e permissões por perfil.

Não incluir nesta versão: marketplace entre assistências, estoque completo, emissão fiscal, contabilidade, pagamento online ou chatbot. Essas funcionalidades podem ser planejadas posteriormente.

## 3. Perfis de acesso

| Perfil | Permissões |
| --- | --- |
| Cliente | Consultar catálogo, solicitar atendimento e acompanhar apenas seu próprio atendimento pelo link individual |
| Administrador | Gerenciar serviços, funcionários, solicitações, OS, responsáveis, orçamentos e configurações |
| Técnico | Consultar OS atribuídas a ele, registrar diagnóstico, atividades e anexos e atualizar etapas técnicas |

Somente o administrador pode gerenciar permissões, registrar decisões comerciais e finalizar a entrega. As permissões devem ser verificadas no servidor, além da interface.

## 4. Fluxo principal

1. O cliente acessa o catálogo da assistência.
2. Escolhe um serviço, solicita uma avaliação ou entra em contato com o técnico.
3. Preenche seus dados e as informações do equipamento.
4. O sistema registra uma solicitação e fornece protocolo e link de acompanhamento.
5. O administrador analisa o pedido e combina o recebimento do aparelho.
6. Ao receber fisicamente o equipamento, confere os dados, registra condições e acessórios e aciona “Gerar OS”.
7. O técnico realiza o diagnóstico e prepara o orçamento.
8. O administrador registra a aprovação ou recusa do cliente, incluindo canal, data e observação.
9. Quando aprovado, o técnico executa o serviço, registra pendências e realiza testes.
10. O equipamento fica pronto para retirada.
11. O administrador registra a entrega e finaliza o atendimento.

O envio do formulário não deve gerar uma OS automaticamente. Uma solicitação representa interesse; a OS representa o equipamento recebido pela assistência.

## 5. Catálogo público

Exibir serviços em cards contendo nome, descrição breve, categorias de equipamentos atendidas e modalidade de preço.

Serviços iniciais de exemplo:

- Formatação e instalação de sistema operacional.
- Limpeza e manutenção preventiva.
- Troca ou instalação de peças.
- Troca de tela e bateria.
- Diagnóstico e reparo eletrônico.

Cada serviço deve admitir preço fixo, “A partir de” ou “Sob avaliação”. Não apresentar estimativas como preço definitivo. O formulário deve preservar o serviço escolhido.

Disponibilizar ações explícitas: “Solicitar serviço”, “Conversar com o técnico” e “Não sei qual é o problema”. A opção de contato deve abrir o canal configurado pela assistência, como WhatsApp, com mensagem inicial relacionada ao serviço.

Permitir cadastrar, editar e desativar serviços. Desativar um serviço não pode apagar seu histórico nos atendimentos existentes.

## 6. Formulário de solicitação

Organizar o preenchimento em etapas curtas: contato, equipamento e problema/revisão.

| Grupo | Campos |
| --- | --- |
| Contato | Nome e telefone obrigatórios; e-mail opcional |
| Equipamento | Categoria obrigatória; marca e modelo quando conhecidos; opção “Não sei informar” |
| Problema | Serviço selecionado, descrição do problema e observações |
| Complementos | Fotos opcionais e identificação do dispositivo, quando disponível |

Os campos devem se adaptar à categoria do aparelho. Número de série e IMEI são opcionais e podem ser completados no recebimento. Não solicitar senhas de desbloqueio, credenciais de contas ou dados sem necessidade para o atendimento.

Exibir resumo antes do envio, validar campos com mensagens claras e impedir submissões duplicadas. Após o envio, mostrar confirmação, protocolo e link individual. Não exigir criação de senha para enviar a solicitação.

## 7. Gestão das solicitações

Criar uma aba “Solicitações” separada da lista de OS, com protocolo, cliente, equipamento, serviço, data e situação.

Situações: Nova, Em análise, Aguardando equipamento, Convertida em OS e Cancelada.

Ao gerar a OS:

- Confirmar recebimento físico do aparelho.
- Conferir equipamento, defeito relatado, acessórios e estado de conservação.
- Permitir anexar fotos de entrada.
- Selecionar o técnico responsável, quando definido.
- Reutilizar os dados cadastrados pelo cliente.
- Gerar número único e vincular a OS à solicitação original.
- Registrar automaticamente a atividade “Equipamento recebido”.

A operação deve ser atômica e impedir mais de uma OS para a mesma solicitação, mesmo em cliques repetidos ou requisições simultâneas. Permitir também abrir uma OS diretamente no balcão, sem solicitação prévia.

## 8. Painel administrativo e tabela de OS

Exibir indicadores resumidos de OS abertas, aguardando aprovação, aguardando peça e prontas para retirada.

Tabela com as colunas: número da OS, cliente, equipamento, serviço, status, técnico responsável, entrada e previsão de entrega. Usar paginação e ordenação.

Disponibilizar busca por número da OS, cliente e equipamento; filtros por status, responsável, período de entrada e atraso; e botão “Nova OS”. Uma OS está atrasada quando possui previsão vencida e ainda não está finalizada ou cancelada.

Cada linha deve ter uma ação visível “Ver OS”. O clique na linha pode ser um atalho, sem ser o único meio de abrir o atendimento. Em telas pequenas, apresentar os dados prioritários em cards.

## 9. Detalhes da OS

Ao abrir a OS, apresentar um card principal com número, status, cliente, contato, equipamento, serviço, técnico, datas e previsão de entrega.

Organizar o restante em seções claras: recebimento, diagnóstico, orçamento, atividades e anexos. No celular, usar uma coluna.

O orçamento deve conter itens de serviço e peças descritas, quantidades, valores unitários e total calculado. A primeira versão não precisa controlar estoque. Registrar a decisão do cliente com responsável pelo registro, data, canal e observação. Uma alteração de valor ou escopo após aprovação exige nova aprovação antes de continuar o reparo.

## 10. Status e regras de transição

| Status | Significado |
| --- | --- |
| Recebido | Equipamento conferido e recebido |
| Em diagnóstico | Problema em investigação |
| Aguardando aprovação | Orçamento apresentado ao cliente |
| Aguardando peça | Reparo aprovado e dependente de peça |
| Em execução | Serviço aprovado em andamento |
| Em testes | Reparo concluído e em verificação |
| Pronto para retirada | Equipamento disponível para devolução |
| Finalizado | Equipamento entregue e atendimento encerrado |
| Cancelado | Atendimento interrompido, com motivo e destinação do aparelho registrados |

Fluxo padrão: Recebido → Em diagnóstico → Aguardando aprovação → Em execução → Em testes → Pronto para retirada → Finalizado.

Permitir alternar entre Em execução e Aguardando peça. Testes com falha podem retornar para Em execução, mediante justificativa. Uma recusa de orçamento deve permitir encaminhar o aparelho para retirada sem reparo, com essa informação explícita. Não iniciar reparo sem aprovação registrada.

Finalizar exige confirmação de entrega. Cancelar exige motivo e registro sobre a devolução ou permanência do equipamento. OS encerradas não aceitam alterações operacionais; eventual reabertura deve ser feita pelo administrador com justificativa e evento no histórico. Não apagar a OS para corrigir um atendimento.

## 11. Histórico de atividades e comentários

Exibir uma linha do tempo dentro da OS. Cada evento deve registrar autor, data/hora, descrição, visibilidade e, quando aplicável, status anterior e novo.

O formulário “Adicionar atualização” deve conter comentário, alteração opcional de status, anexos opcionais e seletor de visibilidade. Usar “Nota interna” como padrão e permitir marcar explicitamente “Visível para o cliente”.

Exemplos:

| Atividade | Status resultante | Visibilidade sugerida |
| --- | --- | --- |
| Equipamento recebido com carregador | Recebido | Cliente |
| Defeito identificado na memória RAM | Em diagnóstico | Interna |
| Aguardando peça chegar; previsão informada pelo fornecedor | Aguardando peça | Cliente |
| Fornecedor confirmou entrega para amanhã | Sem alteração | Interna |
| Conserto realizado; iniciando testes | Em testes | Cliente |
| Testes concluídos; disponível para retirada | Pronto para retirada | Cliente |
| Equipamento entregue; atendimento finalizado | Finalizado | Cliente |

Comentários não precisam mudar o status. Toda mudança de status deve gerar um evento automático, mesmo quando feita fora do formulário de comentário. Gravar alteração e evento na mesma transação, sem duplicar eventos no reenvio da operação.

Preservar os registros originais. Correções devem ser adicionadas como novos eventos vinculados ao registro corrigido. Anexos devem respeitar a visibilidade do evento.

## 12. Acompanhamento do cliente

O link individual deve apresentar protocolo, serviço, identificação resumida do equipamento, status público, previsão quando existente e atualizações liberadas pela equipe.

Usar token aleatório não previsível, independente do número sequencial da OS, com possibilidade de revogação pelo administrador. Após a conversão, o acompanhamento deve continuar vinculado à OS.

Notas internas, custos internos e dados de outros clientes nunca devem ser retornados pela API pública. Permitir ao cliente acessar o contato da assistência. A aprovação online do orçamento pode ficar para uma versão futura; nesta versão, a equipe registra a decisão recebida pelo canal de contato.

## 13. Orientação a objetos

Modelar o domínio com objetos que representem os conceitos do negócio e protejam suas regras, evitando classes usadas somente como recipientes de dados.

| Objeto | Responsabilidade |
| --- | --- |
| Cliente | Identidade e contato do solicitante |
| Equipamento | Categoria, marca, modelo e identificação do dispositivo |
| Servico | Oferta do catálogo e modalidade de preço |
| Solicitacao | Pedido inicial e vínculo com a OS gerada |
| OrdemServico | Ciclo de atendimento, responsável, orçamento e transições válidas |
| Orcamento e ItemOrcamento | Composição de valores, versões e decisão do cliente |
| Atividade | Registro cronológico e sua visibilidade |
| Anexo | Arquivo, metadados e vínculo com atividade ou recebimento |
| Usuario | Funcionário autenticado e perfil de acesso |

Aplicar encapsulamento, composição e responsabilidade única. Por exemplo, a OrdemServico deve validar uma transição antes de aceitá-la e impedir execução sem orçamento aprovado. A camada de aplicação coordena autorização, persistência e transações.

Usar categoria do equipamento e perfil de usuário como atributos, sem criar subclasses para cada variação sem comportamento próprio. Não forçar herança, interfaces ou padrões de projeto sem necessidade concreta.

Separar interface, aplicação, domínio e persistência em módulos simples. Manter regras de negócio fora de componentes visuais e controladores HTTP. A primeira versão pode ser um monólito modular; não exige microsserviços, filas ou arquitetura distribuída.

## 14. Affordance e usabilidade

Aplicar affordance por meio de controles reconhecíveis e sinais visuais que indiquem a ação disponível. O usuário deve conseguir identificar o que é clicável, editável, selecionável e indisponível.

| Elemento | Comportamento esperado |
| --- | --- |
| Botão principal | Destaque visual e verbo explícito, como “Solicitar serviço” ou “Salvar atualização” |
| Botão secundário | Menor destaque para contato, voltar e cancelar edição |
| Campo de formulário | Borda perceptível, rótulo permanente e exemplo quando necessário |
| Anexo | Botão “Adicionar fotos”, além de arrastar e soltar opcional |
| Linha da OS | Realce ao passar o cursor, foco por teclado e ação “Ver OS” |
| Status | Etiqueta com texto e cor; nunca depender apenas de cor |
| Controle indisponível | Explicar o requisito faltante, como aprovação do orçamento |
| Salvamento | Indicador de progresso, bloqueio de cliques duplicados e confirmação de sucesso |
| Erro | Mensagem próxima ao campo e preservação do conteúdo preenchido |

Não esconder ações essenciais em gestos, ícones sem rótulo ou menus difíceis de descobrir. Não usar aparência de botão em elementos sem ação. Garantir operação por teclado, foco visível e rótulos acessíveis. Recursos importantes não podem depender de hover.

## 15. Design minimalista

- Fundo claro, superfícies neutras e uma cor principal de destaque.
- Cores de situação usadas com moderação e acompanhadas de texto.
- Tipografia legível, hierarquia clara e espaçamento consistente.
- Cards com bordas discretas, sem excesso de sombras ou efeitos.
- Uma ação principal por contexto e ações secundárias agrupadas.
- Conteúdo essencial em primeiro plano; detalhes extensos em seções secundárias.
- Layout responsivo para desktop, tablet e celular.
- Ícones consistentes, acompanhados de texto nas ações principais.
- Estados vazios com orientação, por exemplo: “Nenhuma solicitação recebida”.
- Confirmação para ações de consequência relevante, como cancelar ou finalizar uma OS.

Minimalismo deve reduzir ruído sem esconder informações necessárias. Evitar animações decorativas, painéis sobrecarregados e navegação profunda.

## 16. Persistência e proteção de dados

Utilizar banco relacional, relacionamentos explícitos, migrações e validações no servidor. Manter valores monetários em representação decimal apropriada, sem ponto flutuante binário para cálculos financeiros.

Armazenar senhas dos funcionários com hash apropriado e utilizar o mecanismo de autenticação do framework escolhido. Proteger uploads com validação de tipo, tamanho, autorização e armazenamento privado. Nunca confiar somente na extensão do arquivo.

Aplicar permissões a cada operação e a cada objeto acessado. Preservar o histórico ao desativar usuários e serviços. Registrar datas de forma consistente e apresentar horários no fuso configurado da assistência, inicialmente America/Sao_Paulo.

Evitar dados pessoais nos logs e expor apenas os dados necessários no acompanhamento público. Documentar configuração, backup e restauração.

## 17. Entregáveis

1. Código-fonte organizado e instruções de execução.
2. Modelo de dados com relacionamentos e migrações.
3. Catálogo, solicitação, acompanhamento e painel administrativo funcionais.
4. Regras de negócio implementadas em objetos do domínio.
5. Dados fictícios para demonstração, sem credenciais fixas de produção.
6. Testes dos fluxos críticos e instruções de validação manual da interface.
7. README explicando instalação, configuração e decisões técnicas.

A tecnologia não está fixada neste documento. Antes da implementação, declarar a stack escolhida e justificar brevemente sua adequação, priorizando recursos nativos do framework e poucas dependências.

## 18. Critérios de aceite

- [ ] O cliente seleciona um serviço e envia uma solicitação com dados persistidos.
- [ ] O envio retorna protocolo e link de acompanhamento individual.
- [ ] A solicitação aparece no painel sem se tornar OS automaticamente.
- [ ] O administrador confirma o recebimento e gera apenas uma OS por solicitação.
- [ ] A tabela de OS permite busca, filtros, paginação e abertura dos detalhes.
- [ ] O técnico autorizado registra diagnóstico e atividades.
- [ ] Um comentário pode ser salvo sem alterar o status.
- [ ] Mudanças de status geram histórico com autor e data/hora.
- [ ] O sistema bloqueia reparo sem aprovação e exige nova aprovação para orçamento alterado.
- [ ] A pendência por peça aparece claramente na tabela e no histórico.
- [ ] Notas e anexos internos não aparecem nem são retornados no acesso público.
- [ ] O cliente não consegue acessar atendimentos de terceiros por troca de identificadores.
- [ ] O atendimento só é finalizado após confirmação de entrega.
- [ ] Reaberturas e correções preservam os registros anteriores.
- [ ] As regras críticas possuem testes de autorização, transição e prevenção de duplicidade.
- [ ] A interface funciona em celular e por teclado, com foco e mensagens claros.
- [ ] Os dados continuam disponíveis após reiniciar a aplicação.

## 19. Diretriz final

Implemente primeiro o fluxo completo: catálogo → solicitação → recebimento → OS → diagnóstico e orçamento → aprovação → execução e testes → retirada → finalização. Priorize clareza, rastreabilidade e facilidade de uso, mantendo a estrutura preparada para evoluir sem criar funcionalidades especulativas.
