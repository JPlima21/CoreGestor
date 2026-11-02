import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Cliente, Equipamento, Solicitacao, OrdemServico, Atividade, Anexo, Orcamento, ItemOrcamento, admin


def anexar(solicitacao, foto, atividade=None, publico=False):
    """Armazena uma foto já validada com nome aleatório, vinculando solicitação, atividade e visibilidade."""
    if foto:
        extension = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}[foto.content_type]
        original = foto.name[:150]
        foto.name = uuid.uuid4().hex + extension
        Anexo.objects.create(solicitacao=solicitacao, atividade=atividade, arquivo=foto, nome=original, tipo=foto.content_type, publico=publico)


@transaction.atomic
def solicitar(dados):
    """Cria cliente, equipamento, solicitação e foto opcional em uma transação.
    
    Retorna a solicitação existente quando a chave de idempotência já foi usada,
    evitando duplicação no reenvio. Não gera uma ordem de serviço automaticamente."""
    existente = Solicitacao.objects.filter(chave=dados['chave']).first()
    if existente:
        return existente
    cliente = Cliente.objects.create(**{k: dados[k] for k in ('nome', 'telefone', 'email')})
    equipamento = Equipamento.objects.create(cliente=cliente, **{k: dados[k] for k in ('categoria', 'marca', 'modelo', 'identificacao')})
    solicitacao = Solicitacao.objects.create(cliente=cliente, equipamento=equipamento, servico=dados['servico'], problema=dados['problema'], chave=dados['chave'])
    anexar(solicitacao, dados.get('foto'), publico=True)
    return solicitacao


@transaction.atomic
def receber(solicitacao, dados, user):
    """Converte uma solicitação ativa em OS após confirmação do recebimento físico.
    
    Exige administrador, bloqueia o registro durante a transação e reutiliza a OS
    caso ela já exista. Registra condições, técnico, previsão, identificação e foto,
    marca a solicitação como convertida e cria o evento de entrada em conjunto."""
    if not admin(user):
        raise PermissionDenied
    solicitacao = Solicitacao.objects.select_for_update().get(pk=solicitacao.pk)
    existente = OrdemServico.objects.filter(solicitacao=solicitacao).first()
    if existente:
        return existente
    if solicitacao.situacao == 'cancelada' or not dados.get('recebido'):
        raise ValidationError('É necessário confirmar o recebimento de uma solicitação ativa.')
    ordem = OrdemServico.objects.create(solicitacao=solicitacao, recebimento=dados['recebimento'], tecnico=dados.get('tecnico'), previsao=dados.get('previsao'))
    solicitacao.situacao = 'convertida'
    solicitacao.save(update_fields=['situacao'])
    if dados.get('identificacao'):
        solicitacao.equipamento.identificacao = dados['identificacao']
        solicitacao.equipamento.save(update_fields=['identificacao'])
    evento = Atividade.objects.create(ordem=ordem, autor=user, descricao='Equipamento recebido. ' + dados['recebimento'], publico=True, novo='recebido')
    anexar(solicitacao, dados.get('foto'), evento, True)
    return ordem


@transaction.atomic
def atualizar(ordem_id, dados, user):
    """Salva comentário, eventual transição de status e anexos da OS atomicamente.
    
    Confere acesso, chave de idempotência e versão para evitar reenvios e alterações
    sobre dados desatualizados. Valida correções e transições sem apagar eventos
    anteriores e aplica aos anexos a visibilidade escolhida para a atualização."""
    ordem = OrdemServico.objects.select_for_update().get(pk=ordem_id)
    ordem.autorizar(user)
    if Atividade.objects.filter(chave=dados['chave'], ordem=ordem).exists():
        return
    if dados['versao'] != ordem.versao:
        raise ValidationError('Esta OS mudou. Atualize a página antes de salvar.')
    anterior = ordem.status
    novo = dados.get('status') or anterior
    if ordem.encerrada and novo == anterior:
        raise ValidationError('Reabra a OS antes de realizar alterações operacionais.')
    ordem.transicionar(novo, user, dados['comentario'], dados.get('entrega'))
    correcao = None
    if dados.get('correcao_de'):
        correcao = ordem.atividades.filter(pk=dados['correcao_de']).first()
        if not correcao:
            raise ValidationError('O evento corrigido deve pertencer a esta OS.')
    if not dados['comentario'].strip() and novo == anterior and not dados.get('foto'):
        raise ValidationError('Escreva um comentário, adicione uma foto ou altere o status.')
    descricao = dados['comentario']
    if novo != anterior:
        descricao = f'{dict(OrdemServico.STATUS)[anterior]} → {ordem.get_status_display()}. ' + descricao
        if anterior == 'aprovacao' and novo == 'pronto':
            descricao += ' Equipamento disponível para retirada sem reparo: orçamento recusado.'
    ordem.versao += 1
    ordem.save()
    evento = Atividade.objects.create(ordem=ordem, autor=user, descricao=descricao, publico=dados['publico'], anterior=anterior if novo != anterior else '', novo=novo if novo != anterior else '', chave=dados['chave'], correcao_de=correcao)
    anexar(ordem.solicitacao, dados.get('foto'), evento, evento.publico)


@transaction.atomic
def editar(ordem_id, user, acao, dados):
    """Executa uma edição autorizada da OS e registra seu evento na mesma transação.
    
    Trata diagnóstico, nova versão de orçamento, decisão comercial e atribuição.
    Decisão e atribuição exigem administrador. Um novo orçamento preserva o antigo
    e suspende etapas de reparo até nova aprovação. Reenvios com a mesma chave não
    duplicam a operação; OS encerradas precisam ser reabertas antes da edição."""
    ordem = OrdemServico.objects.select_for_update().get(pk=ordem_id)
    ordem.autorizar(user)
    chave = dados.get('chave', uuid.uuid4())
    if Atividade.objects.filter(ordem=ordem, chave=chave).exists():
        return
    if ordem.encerrada:
        raise ValidationError('OS encerrada. Reabra com justificativa antes de editar.')
    status_anterior = ordem.status
    if acao == 'diagnostico':
        ordem.diagnostico = dados['diagnostico']
        texto = 'Diagnóstico registrado: ' + ordem.diagnostico
    elif acao == 'orcamento':
        anterior = ordem.orcamentos.order_by('-versao').first()
        orcamento = Orcamento.objects.create(ordem=ordem, versao=anterior.versao + 1 if anterior else 1)
        for descricao, quantidade, valor in dados['itens']:
            ItemOrcamento.objects.create(orcamento=orcamento, descricao=descricao, quantidade=quantidade, valor=valor)
        texto = f'Orçamento v{orcamento.versao} criado; nova aprovação necessária.'
        if ordem.status not in ('recebido', 'diagnostico', 'aprovacao'):
            texto += f' {ordem.get_status_display()} → Aguardando aprovação.'
            ordem.status = 'aprovacao'
    elif acao == 'decisao':
        if not admin(user):
            raise PermissionDenied
        orcamento = ordem.orcamentos.order_by('-versao').first()
        if not orcamento or orcamento.decisao != 'pendente':
            raise ValidationError('Não há orçamento pendente. Crie uma nova versão para alterar a decisão.')
        for campo in ('decisao', 'canal', 'observacao'):
            setattr(orcamento, campo, dados[campo])
        orcamento.registrado_por, orcamento.decidido_em = user, timezone.now()
        orcamento.save()
        texto = f'Orçamento v{orcamento.versao}: {orcamento.get_decisao_display()} via {orcamento.canal}. {orcamento.observacao}'
    elif acao == 'atribuir':
        if not admin(user):
            raise PermissionDenied
        ordem.tecnico, ordem.previsao = dados['tecnico'], dados['previsao']
        texto = f'Responsável e previsão atualizados: {ordem.tecnico or "Não atribuído"}; {ordem.previsao or "Sem previsão"}.'
    else:
        raise ValidationError('Operação inválida.')
    ordem.versao += 1
    ordem.save()
    if texto:
        Atividade.objects.create(ordem=ordem, autor=user, descricao=texto, chave=chave, anterior=status_anterior if ordem.status != status_anterior else '', novo=ordem.status if ordem.status != status_anterior else '')
