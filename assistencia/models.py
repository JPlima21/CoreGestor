import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import models
from django.utils import timezone


def token():
    """Gera um token aleatório seguro para o link individual de acompanhamento."""
    return secrets.token_urlsafe(32)


def admin(user):
    """Indica se o usuário está autenticado, ativo e possui perfil de administrador."""
    return user.is_authenticated and user.is_active and user.is_superuser


class Configuracao(models.Model):
    nome = models.CharField(max_length=100, default='CoreGestor Assistência')
    telefone = models.CharField(max_length=20, default='5511999999999')
    endereco = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        """Salva a identidade da assistência no registro de ID 1, mantendo uma configuração por instalação."""
        self.pk = 1
        super().save(*args, **kwargs)


class Cliente(models.Model):
    nome = models.CharField(max_length=120)
    telefone = models.CharField(max_length=25)
    email = models.EmailField(blank=True)

    def __str__(self):
        """Retorna o nome do cliente para exibição em listas e formulários."""
        return self.nome


class Equipamento(models.Model):
    CATEGORIAS = [('computador', 'Computador'), ('notebook', 'Notebook'), ('celular', 'Celular')]
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS)
    marca = models.CharField(max_length=80, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    identificacao = models.CharField('Número de série / IMEI', max_length=100, blank=True)

    def __str__(self):
        """Monta a descrição do equipamento com categoria, marca e modelo disponíveis."""
        return ' '.join(filter(None, [self.get_categoria_display(), self.marca, self.modelo]))


class Servico(models.Model):
    nome = models.CharField(max_length=120)
    descricao = models.TextField()
    categorias = models.CharField(max_length=120, default='Computadores, notebooks e celulares')
    modalidade = models.CharField(max_length=20, choices=[('fixo', 'Preço fixo'), ('partir', 'A partir de'), ('avaliacao', 'Sob avaliação')], default='avaliacao')
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ativo = models.BooleanField(default=True)

    def clean(self):
        """Rejeita preços negativos durante a validação do serviço."""
        if self.valor < 0:
            raise ValidationError('O valor não pode ser negativo.')

    def __str__(self):
        """Retorna o nome do serviço para exibição no catálogo e nos formulários."""
        return self.nome


class Solicitacao(models.Model):
    SITUACOES = [('nova', 'Nova'), ('analise', 'Em análise'), ('aguardando', 'Aguardando equipamento'), ('convertida', 'Convertida em OS'), ('cancelada', 'Cancelada')]
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT)
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, null=True, blank=True)
    problema = models.TextField()
    situacao = models.CharField(max_length=20, choices=SITUACOES, default='nova')
    criado = models.DateTimeField(auto_now_add=True)
    token = models.CharField(max_length=64, default=token, unique=True)
    link_ativo = models.BooleanField(default=True)
    chave = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    @property
    def protocolo(self):
        """Formata o ID persistido como protocolo de atendimento, por exemplo AT-000001."""
        return f'AT-{self.pk:06d}'


class OrdemServico(models.Model):
    STATUS = [('recebido', 'Recebido'), ('diagnostico', 'Em diagnóstico'), ('aprovacao', 'Aguardando aprovação'), ('peca', 'Aguardando peça'), ('execucao', 'Em execução'), ('testes', 'Em testes'), ('pronto', 'Pronto para retirada'), ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado')]
    solicitacao = models.OneToOneField(Solicitacao, on_delete=models.PROTECT, related_name='ordem')
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='recebido')
    entrada = models.DateTimeField(auto_now_add=True)
    previsao = models.DateField(null=True, blank=True)
    recebimento = models.TextField()
    diagnostico = models.TextField(blank=True)
    versao = models.PositiveIntegerField(default=1)

    @property
    def numero(self):
        """Formata o ID persistido como número de OS, por exemplo OS-000001."""
        return f'OS-{self.pk:06d}'

    @property
    def encerrada(self):
        """Indica se a OS está finalizada ou cancelada, bloqueando alterações operacionais comuns."""
        return self.status in ('finalizado', 'cancelado')

    @property
    def atrasada(self):
        """Indica atraso quando a previsão venceu no fuso configurado e a OS ainda não foi encerrada."""
        return bool(self.previsao and self.previsao < timezone.localdate() and not self.encerrada)

    def autorizar(self, user):
        """Permite acesso ao administrador ou técnico ativo atribuído à OS; caso contrário, lança PermissionDenied."""
        if not user.is_active or not (admin(user) or self.tecnico_id == user.pk):
            raise PermissionDenied

    def transicionar(self, novo, user, justificativa='', entrega=False):
        """Valida e altera o status da OS em memória, sem salvar ou criar eventos.
        
        Confere autorização, sequência de etapas, aprovação do orçamento e requisitos
        de entrega, cancelamento, retorno de testes e reabertura. Lança ValidationError
        ou PermissionDenied quando a operação não é permitida. A camada de serviços
        salva o novo estado e seu histórico na mesma transação."""
        self.autorizar(user)
        if novo == self.status:
            return
        if self.encerrada:
            if not admin(user) or novo != 'diagnostico' or not justificativa.strip():
                raise ValidationError('Reabertura exige administrador e justificativa.')
        else:
            fluxo = {'recebido': ['diagnostico'], 'diagnostico': ['aprovacao'], 'aprovacao': ['execucao', 'pronto'], 'execucao': ['peca', 'testes'], 'peca': ['execucao'], 'testes': ['pronto', 'execucao'], 'pronto': ['finalizado']}
            if novo != 'cancelado' and novo not in fluxo.get(self.status, []):
                raise ValidationError('Transição não permitida a partir da etapa atual.')
            if novo in ('cancelado', 'finalizado') and not admin(user):
                raise PermissionDenied
            if novo == 'cancelado' and not justificativa.strip():
                raise ValidationError('Informe o motivo e a destinação do equipamento.')
            if novo == 'finalizado' and not entrega:
                raise ValidationError('Confirme a entrega do equipamento.')
            orcamento = self.orcamentos.order_by('-versao').first()
            if novo in ('execucao', 'peca', 'testes') and (not orcamento or orcamento.decisao != 'aprovado'):
                raise ValidationError('É necessário orçamento aprovado para executar o reparo.')
            if novo == 'aprovacao' and (not orcamento or not orcamento.itens.exists()):
                raise ValidationError('Cadastre os itens do orçamento primeiro.')
            if self.status == 'aprovacao' and novo == 'pronto' and (not orcamento or orcamento.decisao != 'recusado'):
                raise ValidationError('Retirada sem reparo exige recusa registrada.')
            if self.status == 'testes' and novo == 'execucao' and not justificativa.strip():
                raise ValidationError('Justifique a falha nos testes.')
        self.status = novo


class Orcamento(models.Model):
    ordem = models.ForeignKey(OrdemServico, on_delete=models.PROTECT, related_name='orcamentos')
    versao = models.PositiveIntegerField()
    decisao = models.CharField(max_length=20, choices=[('pendente', 'Pendente'), ('aprovado', 'Aprovado'), ('recusado', 'Recusado')], default='pendente')
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    decidido_em = models.DateTimeField(null=True)
    canal = models.CharField(max_length=80, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['ordem', 'versao'], name='orcamento_versao_unica')]

    @property
    def total(self):
        """Calcula a soma das quantidades multiplicadas pelos valores unitários usando Decimal."""
        return sum((i.quantidade * i.valor for i in self.itens.all()), Decimal('0.00'))


class ItemOrcamento(models.Model):
    orcamento = models.ForeignKey(Orcamento, on_delete=models.PROTECT, related_name='itens')
    descricao = models.CharField(max_length=200)
    quantidade = models.PositiveIntegerField(default=1)
    valor = models.DecimalField(max_digits=10, decimal_places=2)


class Atividade(models.Model):
    ordem = models.ForeignKey(OrdemServico, on_delete=models.PROTECT, related_name='atividades')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    criado = models.DateTimeField(auto_now_add=True)
    descricao = models.TextField()
    publico = models.BooleanField(default=False)
    anterior = models.CharField(max_length=20, blank=True)
    novo = models.CharField(max_length=20, blank=True)
    chave = models.UUIDField(default=uuid.uuid4, unique=True)
    correcao_de = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ['-criado']


class Anexo(models.Model):
    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.PROTECT, related_name='anexos')
    atividade = models.ForeignKey(Atividade, on_delete=models.PROTECT, null=True, blank=True, related_name='anexos')
    arquivo = models.FileField(upload_to='anexos/%Y/%m')
    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=30)
    publico = models.BooleanField(default=False)
