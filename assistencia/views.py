import secrets
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Configuracao, Servico, Solicitacao, OrdemServico, Anexo, admin, token
from .forms import SolicitarForm, ReceberForm, AtualizarForm, DiagnosticoForm, OrcamentoForm, DecisaoForm, SituacaoForm, AtribuirForm
from . import services


def contexto(request):
    """Disponibiliza identidade da assistência, indicação de administrador e link de contato aos templates."""
    config = Configuracao.objects.filter(pk=1).first()
    return {'empresa': config, 'administrador': admin(request.user), 'contato': 'https://wa.me/' + (config.telefone if config else '5511999999999')}


def catalogo(request):
    """Renderiza o catálogo público somente com os serviços ativos."""
    return render(request, 'assistencia/catalogo.html', {'servicos': Servico.objects.filter(ativo=True)})


def solicitar(request):
    """Exibe e valida o pedido público, confere a chave emitida à sessão e redireciona ao acompanhamento após gravar."""
    form = SolicitarForm(request.POST or None, request.FILES or None, initial={'servico': request.GET.get('servico')})
    if request.method == 'POST' and form.is_valid():
        if str(form.cleaned_data['chave']) not in request.session.get('solicitar_chaves', []):
            form.add_error(None, 'Formulário expirado. Reabra a página.')
        else:
            pedido = services.solicitar(form.cleaned_data)
            return redirect('acompanhar', token=pedido.token)
    if request.method == 'GET':
        request.session['solicitar_chaves'] = (request.session.get('solicitar_chaves', []) + [str(form['chave'].value())])[-10:]
    return render(request, 'assistencia/solicitar.html', {'form': form})


def acompanhar(request, token):
    """Renderiza o acompanhamento pelo token ativo, expondo somente campos públicos.
    
    Mantém o vínculo após a conversão em OS, sinaliza retirada sem reparo e filtra
    notas e anexos internos. Desativa cache e envio de referência para proteger o link."""
    pedido = get_object_or_404(Solicitacao.objects.select_related('equipamento', 'servico'), token=token, link_ativo=True)
    os = OrdemServico.objects.filter(solicitacao=pedido).first()
    dados = {'protocolo': pedido.protocolo, 'servico': str(pedido.servico or 'Avaliação técnica'), 'equipamento': str(pedido.equipamento), 'status': os.get_status_display() if os else pedido.get_situacao_display(), 'previsao': os.previsao if os else None}
    if os and os.status in ('pronto', 'finalizado'):
        orcamento = os.orcamentos.order_by('-versao').first()
        if orcamento and orcamento.decisao == 'recusado':
            dados['status'] += ' · Sem reparo (orçamento recusado)'
    eventos = list(os.atividades.filter(publico=True).values('id', 'descricao', 'criado')) if os else []
    fotos = pedido.anexos.filter(publico=True).filter(Q(atividade__isnull=True) | Q(atividade__publico=True)).values('id', 'nome')
    response = render(request, 'assistencia/acompanhar.html', {'dados': dados, 'eventos': eventos, 'fotos': fotos, 'token': token})
    response['Cache-Control'], response['Referrer-Policy'] = 'no-store', 'no-referrer'
    return response


@login_required
def painel(request):
    """Lista OS autorizadas com indicadores, busca, filtros, ordenação permitida e paginação de 12 registros."""
    ordens = OrdemServico.objects.select_related('solicitacao__cliente', 'solicitacao__equipamento', 'solicitacao__servico', 'tecnico')
    if not admin(request.user):
        ordens = ordens.filter(tecnico=request.user)
    indicadores = {s: ordens.filter(status=s).count() for s in ['aprovacao', 'peca', 'pronto']}
    indicadores['abertas'] = ordens.exclude(status__in=['finalizado', 'cancelado']).count()
    busca = request.GET.get('q', '').strip()
    if busca:
        filtro = Q(solicitacao__cliente__nome__icontains=busca) | Q(solicitacao__equipamento__modelo__icontains=busca) | Q(solicitacao__equipamento__marca__icontains=busca) | Q(solicitacao__equipamento__categoria__icontains=busca)
        numero = busca.upper().replace('OS-', '')
        if numero.isdigit():
            filtro |= Q(pk=int(numero))
        ordens = ordens.filter(filtro)
    for campo in ('status', 'tecnico'):
        valor = request.GET.get(campo)
        if valor and (campo != 'tecnico' or valor.isdigit()):
            ordens = ordens.filter(**{campo: valor})
    from datetime import date
    for parametro, campo in [('inicio', 'entrada__date__gte'), ('fim', 'entrada__date__lte')]:
        try:
            if request.GET.get(parametro):
                ordens = ordens.filter(**{campo: date.fromisoformat(request.GET[parametro])})
        except ValueError:
            pass
    if request.GET.get('atrasadas'):
        ordens = ordens.filter(previsao__lt=timezone.localdate()).exclude(status__in=['finalizado', 'cancelado'])
    ordenar = request.GET.get('ordenar', '-entrada')
    if ordenar not in ['entrada', '-entrada', 'previsao', '-previsao', 'pk', '-pk']:
        ordenar = '-entrada'
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'assistencia/painel.html', {'pagina': Paginator(ordens.order_by(ordenar), 12).get_page(request.GET.get('page')), 'indicadores': indicadores, 'status_opcoes': OrdemServico.STATUS, 'tecnicos': AtribuirForm.base_fields['tecnico'].queryset, 'filtros': request.GET, 'query': params.urlencode()})


@login_required
def solicitacoes(request):
    """Lista solicitações para o administrador, com filtro de situação e paginação de 15 registros."""
    if not admin(request.user):
        raise PermissionDenied
    pedidos = Solicitacao.objects.select_related('cliente', 'equipamento', 'servico').order_by('-criado')
    if request.GET.get('situacao') in dict(Solicitacao.SITUACOES):
        pedidos = pedidos.filter(situacao=request.GET['situacao'])
    return render(request, 'assistencia/solicitacoes.html', {'pagina': Paginator(pedidos, 15).get_page(request.GET.get('page')), 'situacoes': Solicitacao.SITUACOES})


@login_required
def receber(request, pk):
    """Permite ao administrador analisar a solicitação, atualizar sua situação e confirmar o recebimento para gerar a OS."""
    if not admin(request.user):
        raise PermissionDenied
    pedido = get_object_or_404(Solicitacao, pk=pk)
    form = ReceberForm(request.POST or None, request.FILES or None, initial={'identificacao': pedido.equipamento.identificacao})
    situacao_form = SituacaoForm(request.POST if request.POST.get('acao') == 'situacao' else None, initial={'situacao': pedido.situacao})
    if request.method == 'POST':
        if request.POST.get('acao') == 'situacao' and situacao_form.is_valid():
            if pedido.situacao != 'convertida':
                pedido.situacao = situacao_form.cleaned_data['situacao']
                pedido.save(update_fields=['situacao'])
                messages.success(request, 'Situação atualizada.')
                return redirect('receber', pk=pk)
        elif form.is_valid():
            try:
                os = services.receber(pedido, form.cleaned_data, request.user)
                return redirect('ordem', pk=os.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, 'assistencia/receber.html', {'pedido': pedido, 'form': form, 'situacao_form': situacao_form})


@login_required
def nova_os(request):
    """Permite ao administrador registrar atendimento de balcão e recebimento físico em uma única transação."""
    if not admin(request.user):
        raise PermissionDenied
    form = SolicitarForm(request.POST or None, request.FILES or None)
    recebimento = ReceberForm(request.POST or None)
    if request.method == 'POST' and form.is_valid() and recebimento.is_valid():
        if str(form.cleaned_data['chave']) not in request.session.get('balcao_chaves', []):
            form.add_error(None, 'Formulário expirado. Reabra a página.')
        else:
            from django.db import transaction
            with transaction.atomic():
                pedido = services.solicitar(form.cleaned_data)
                os = services.receber(pedido, recebimento.cleaned_data, request.user)
            return redirect('ordem', pk=os.pk)
    if request.method == 'GET':
        request.session['balcao_chaves'] = (request.session.get('balcao_chaves', []) + [str(form['chave'].value())])[-10:]
    return render(request, 'assistencia/nova_os.html', {'form': form, 'recebimento': recebimento})


@login_required
def ordem(request, pk):
    """Verifica acesso à OS, exibe detalhes e histórico e encaminha os formulários válidos aos serviços transacionais."""
    os = get_object_or_404(OrdemServico.objects.select_related('solicitacao__cliente', 'solicitacao__equipamento', 'solicitacao__servico', 'tecnico'), pk=pk)
    os.autorizar(request.user)
    forms = {'atualizar': AtualizarForm(initial={'versao': os.versao}), 'diagnostico': DiagnosticoForm(initial={'diagnostico': os.diagnostico}), 'orcamento': OrcamentoForm(), 'decisao': DecisaoForm(), 'atribuir': AtribuirForm(initial={'tecnico': os.tecnico, 'previsao': os.previsao})}
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao not in forms:
            raise Http404
        form = type(forms[acao])(request.POST, request.FILES)
        forms[acao] = form
        if form.is_valid():
            try:
                if acao == 'atualizar':
                    services.atualizar(pk, form.cleaned_data, request.user)
                else:
                    services.editar(pk, request.user, acao, form.cleaned_data)
                messages.success(request, 'Alteração salva com sucesso.')
                return redirect('ordem', pk=pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, 'assistencia/ordem.html', {'os': os, 'forms': forms, 'orcamentos': os.orcamentos.prefetch_related('itens').order_by('-versao'), 'eventos': os.atividades.select_related('autor').prefetch_related('anexos'), 'fotos': os.solicitacao.anexos.filter(atividade__isnull=True)})


@login_required
@require_POST
def revogar(request, pk):
    """Substitui o token de acompanhamento via POST autorizado, invalidando o link anterior e gerando um novo."""
    if not admin(request.user):
        raise PermissionDenied
    pedido = get_object_or_404(Solicitacao, pk=pk)
    pedido.token = token()
    pedido.save(update_fields=['token'])
    messages.success(request, 'Link anterior revogado. Um novo link foi gerado.')
    return redirect('ordem', pk=pedido.ordem.pk) if hasattr(pedido, 'ordem') else redirect('receber', pk=pk)


def anexo(request, pk):
    """Autoriza o download pelo token público válido ou perfil da equipe e entrega o arquivo privado sem cache."""
    foto = get_object_or_404(Anexo.objects.select_related('solicitacao', 'atividade'), pk=pk)
    chave = request.GET.get('token')
    publico = foto.publico and (not foto.atividade_id or foto.atividade.publico)
    acesso = publico and foto.solicitacao.link_ativo and chave and secrets.compare_digest(chave, foto.solicitacao.token)
    if not acesso:
        if not request.user.is_authenticated:
            raise Http404
        os = OrdemServico.objects.filter(solicitacao=foto.solicitacao).first()
        if not admin(request.user) and (not os or os.tecnico_id != request.user.pk or not request.user.is_active):
            raise Http404
    response = FileResponse(foto.arquivo.open('rb'), content_type=foto.tipo, as_attachment=True, filename=foto.nome)
    response['X-Content-Type-Options'], response['Cache-Control'] = 'nosniff', 'no-store'
    return response
