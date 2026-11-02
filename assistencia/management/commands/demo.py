import secrets
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from assistencia.models import Configuracao, Servico, Cliente, Equipamento, Solicitacao, OrdemServico, Atividade, Orcamento, ItemOrcamento


class Command(BaseCommand):
    help = 'Cria catálogo e atendimentos fictícios; senhas aleatórias são exibidas somente na criação.'

    @transaction.atomic
    def handle(self, *args, **options):
        """Cria catálogo, usuários nativos do Django e atendimentos fictícios; exibe senhas aleatórias apenas ao criar os usuários."""
        Configuracao.objects.get_or_create(pk=1)
        exemplos = [
            ('Formatação e sistema', 'Seu computador mais leve, organizado e pronto para acompanhar sua rotina.', 'partir', '120.00', 'Computadores e notebooks'),
            ('Limpeza preventiva', 'Mais desempenho e menos aquecimento, com cuidado por dentro e por fora.', 'partir', '90.00', 'Computadores e notebooks'),
            ('Troca e instalação de peças', 'Um novo fôlego para seu equipamento com os componentes certos.', 'avaliacao', '0', 'Computadores e notebooks'),
            ('Troca de tela e bateria', 'Volte a enxergar tudo com clareza e tenha energia para o seu dia.', 'avaliacao', '0', 'Celulares e notebooks'),
            ('Diagnóstico e reparo', 'Uma análise cuidadosa para encontrar a origem do problema.', 'avaliacao', '0', 'Computadores, notebooks e celulares'),
        ]
        servicos = []
        for nome, descricao, modalidade, valor, categorias in exemplos:
            servico, _ = Servico.objects.get_or_create(nome=nome, defaults={'descricao': descricao, 'modalidade': modalidade, 'valor': Decimal(valor), 'categorias': categorias})
            servicos.append(servico)
        usuarios = []
        for username, superuser, nome in [('admin_demo', True, 'Administrador'), ('tecnico_demo', False, 'Lucas')]:
            user, criado = get_user_model().objects.get_or_create(username=username, defaults={'is_superuser': superuser, 'is_staff': superuser, 'first_name': nome})
            if criado:
                senha = secrets.token_urlsafe(15)
                user.set_password(senha)
                user.save()
                self.stdout.write(f'Usuário: {username} | Senha temporária: {senha}')
            usuarios.append(user)
        if not Solicitacao.objects.exists():
            for i, (nome, categoria, marca, modelo, status) in enumerate([
                ('Mariana Costa', 'notebook', 'Dell', 'Inspiron 15', 'diagnostico'),
                ('Rafael Almeida', 'celular', 'Samsung', 'Galaxy A54', 'aprovacao'),
                ('Camila Santos', 'computador', 'Lenovo', 'ThinkCentre', 'peca'),
                ('Pedro Oliveira', 'notebook', 'Acer', 'Aspire 5', 'pronto'),
                ('Juliana Lima', 'celular', 'Apple', 'iPhone 12', 'recebido'),
                ('Bruno Ferreira', 'notebook', 'Asus', 'VivoBook', None),
            ]):
                cliente = Cliente.objects.create(nome=nome, telefone='11900000000', email=f'demo{i}@example.invalid')
                equipamento = Equipamento.objects.create(cliente=cliente, categoria=categoria, marca=marca, modelo=modelo)
                pedido = Solicitacao.objects.create(cliente=cliente, equipamento=equipamento, servico=servicos[i % len(servicos)], problema='Equipamento apresenta falhas intermitentes. Dados fictícios para demonstração.', situacao='convertida' if status else 'nova')
                if status:
                    os = OrdemServico.objects.create(solicitacao=pedido, tecnico=usuarios[1], status=status, recebimento='Recebido com carregador. Marcas leves de uso.', previsao=timezone.localdate() + timedelta(days=i - 1))
                    Atividade.objects.create(ordem=os, autor=usuarios[0], descricao='Equipamento recebido com carregador.', publico=True, novo='recebido')
                    if status != 'recebido':
                        Atividade.objects.create(ordem=os, autor=usuarios[1], descricao=f'Demonstração: atendimento em {os.get_status_display()}.', publico=True, anterior='recebido', novo=status)
                    if status in ('aprovacao', 'peca', 'pronto'):
                        orcamento = Orcamento.objects.create(ordem=os, versao=1, decisao='pendente' if status == 'aprovacao' else 'aprovado', registrado_por=usuarios[0] if status != 'aprovacao' else None, decidido_em=timezone.now() if status != 'aprovacao' else None, canal='Telefone' if status != 'aprovacao' else '')
                        ItemOrcamento.objects.create(orcamento=orcamento, descricao='Serviço técnico de demonstração', quantidade=1, valor=Decimal('150'))
        self.stdout.write(self.style.SUCCESS('Demonstração pronta. Acesse /entrar/ e altere as senhas. Não use estes dados em produção.'))
