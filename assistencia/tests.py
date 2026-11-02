import uuid
from decimal import Decimal
from io import BytesIO
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Cliente, Equipamento, Solicitacao, OrdemServico, Servico, Atividade, Orcamento, Anexo
from .forms import OrcamentoForm, validar_foto
from . import services


class FluxosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Prepara usuários de diferentes perfis, serviço, cliente, equipamento e solicitação compartilhados pelos testes."""
        User = get_user_model()
        cls.admin = User.objects.create_superuser('admin', password='SenhaAleatoria!123')
        cls.tecnico = User.objects.create_user('tecnico', password='SenhaAleatoria!123')
        cls.outro = User.objects.create_user('outro', password='SenhaAleatoria!123')
        cls.servico = Servico.objects.create(nome='Limpeza', descricao='Limpeza preventiva')
        cls.cliente = Cliente.objects.create(nome='Cliente privado', telefone='21987654321', email='sigilo@example.invalid')
        cls.equipamento = Equipamento.objects.create(cliente=cls.cliente, categoria='notebook', marca='Dell', modelo='Inspiron')
        cls.pedido = Solicitacao.objects.create(cliente=cls.cliente, equipamento=cls.equipamento, servico=cls.servico, problema='Não liga')

    def receber(self):
        """Cria ou recupera a OS de teste usando o recebimento autorizado pelo administrador."""
        return services.receber(self.pedido, {'recebido': True, 'recebimento': 'Com carregador, bom estado.', 'tecnico': self.tecnico}, self.admin)

    def atualizar(self, os, status='', comentario='Atualização de teste', user=None, **extra):
        """Executa uma atualização de teste com chave única e versão atual, permitindo variar status, autor e dados adicionais."""
        os.refresh_from_db()
        dados = {'chave': uuid.uuid4(), 'versao': os.versao, 'status': status, 'comentario': comentario, 'publico': False, 'entrega': False, **extra}
        services.atualizar(os.pk, dados, user or self.tecnico)
        os.refresh_from_db()
        return dados

    def orcamento(self, os):
        """Cadastra um orçamento de teste com quantidade e preço decimal conhecidos."""
        services.editar(os.pk, self.tecnico, 'orcamento', {'itens': [('Limpeza', 2, Decimal('45.10'))]})

    def aprovar(self, os, decisao='aprovado'):
        """Registra, como administrador, a aprovação ou recusa do orçamento no cenário de teste."""
        services.editar(os.pk, self.admin, 'decisao', {'decisao': decisao, 'canal': 'Telefone', 'observacao': 'Cliente informou sua decisão.'})

    def test_fluxo_completo_e_reabertura(self):
        """Verifica o fluxo até entrega e reabertura, incluindo bloqueios por aprovação, permissão e justificativa ausentes."""
        os = self.receber()
        self.atualizar(os, 'diagnostico')
        self.orcamento(os)
        self.assertEqual(os.orcamentos.first().total, Decimal('90.20'))
        self.atualizar(os, 'aprovacao')
        with self.assertRaises(ValidationError):
            self.atualizar(os, 'execucao')
        self.aprovar(os)
        self.atualizar(os, 'execucao')
        self.atualizar(os, 'peca')
        self.atualizar(os, 'execucao')
        self.atualizar(os, 'testes')
        with self.assertRaises(ValidationError):
            self.atualizar(os, 'execucao', comentario='')
        self.atualizar(os, 'execucao', comentario='Falhou no teste de estresse')
        self.atualizar(os, 'testes')
        self.atualizar(os, 'pronto')
        with self.assertRaises(PermissionDenied):
            self.atualizar(os, 'finalizado', entrega=True)
        with self.assertRaises(ValidationError):
            self.atualizar(os, 'finalizado', user=self.admin)
        self.atualizar(os, 'finalizado', user=self.admin, entrega=True)
        eventos = os.atividades.count()
        with self.assertRaises(ValidationError):
            self.atualizar(os, comentario='Alteração em OS fechada')
        with self.assertRaises(ValidationError):
            self.atualizar(os, 'diagnostico', user=self.admin, comentario='')
        self.atualizar(os, 'diagnostico', user=self.admin, comentario='Retorno com falha intermitente')
        self.assertEqual(os.atividades.count(), eventos + 1)

    def test_recebimento_idempotente_e_restricao_banco(self):
        """Confere que reenvios reutilizam a OS e que a restrição do banco impede uma segunda OS para a solicitação."""
        os = self.receber()
        self.assertEqual(self.receber().pk, os.pk)
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(os.atividades.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrdemServico.objects.create(solicitacao=self.pedido, recebimento='Duplicada')

    def test_comentario_idempotente_sem_mudar_status(self):
        """Confere que um comentário não altera o status e que seu reenvio não duplica o evento."""
        os = self.receber()
        dados = self.atualizar(os, comentario='Nota interna confidencial')
        services.atualizar(os.pk, dados, self.tecnico)
        self.assertEqual(os.status, 'recebido')
        self.assertEqual(os.atividades.filter(chave=dados['chave']).count(), 1)

    def test_conflito_versao_nao_sobrescreve(self):
        """Verifica que uma atualização com versão antiga é rejeitada sem sobrescrever alterações recentes."""
        os = self.receber()
        versao = os.versao
        self.atualizar(os)
        with self.assertRaises(ValidationError):
            self.atualizar(os, versao=versao)

    def test_novo_orcamento_suspende_execucao(self):
        """Confere que uma nova versão preserva o orçamento anterior e bloqueia o reparo até nova aprovação."""
        os = self.receber()
        self.atualizar(os, 'diagnostico')
        self.orcamento(os)
        self.atualizar(os, 'aprovacao')
        self.aprovar(os)
        self.atualizar(os, 'execucao')
        self.orcamento(os)
        os.refresh_from_db()
        self.assertEqual(os.status, 'aprovacao')
        self.assertEqual(os.orcamentos.count(), 2)
        with self.assertRaises(ValidationError):
            self.atualizar(os, 'execucao')
        self.assertEqual(os.orcamentos.get(versao=1).decisao, 'aprovado')

    def test_recusa_permite_retirada_sem_reparo(self):
        """Verifica o encaminhamento para retirada sem reparo após a recusa do orçamento."""
        os = self.receber()
        self.atualizar(os, 'diagnostico')
        self.orcamento(os)
        self.atualizar(os, 'aprovacao')
        self.aprovar(os, 'recusado')
        self.atualizar(os, 'pronto', comentario='Retirada sem reparo por recusa do orçamento', publico=True)
        self.assertEqual(os.status, 'pronto')

    def test_autorizacao_por_objeto_e_decisao(self):
        """Confere isolamento entre técnicos e bloqueio de decisões comerciais e telas administrativas sem permissão."""
        os = self.receber()
        with self.assertRaises(PermissionDenied):
            self.atualizar(os, user=self.outro)
        with self.assertRaises(PermissionDenied):
            services.editar(os.pk, self.tecnico, 'decisao', {'decisao': 'aprovado'})
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(reverse('ordem', args=[os.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('painel')), os.numero)
        self.assertEqual(self.client.get(reverse('solicitacoes')).status_code, 403)
        self.assertEqual(self.client.get('/gestao/').status_code, 302)

    def test_publico_nao_expoe_internos_e_revogacao(self):
        """Verifica que o acompanhamento oculta notas e contatos privados e que links revogados deixam de funcionar."""
        os = self.receber()
        self.atualizar(os, comentario='SEGREDO INTERNO 123')
        self.atualizar(os, comentario='Atualização pública de teste', publico=True)
        response = self.client.get(reverse('acompanhar', args=[self.pedido.token]))
        self.assertContains(response, 'Atualização pública de teste')
        for segredo in ['SEGREDO INTERNO 123', self.cliente.email, self.cliente.telefone, self.cliente.nome]:
            self.assertNotContains(response, segredo)
        self.assertEqual(self.client.get('/acompanhar/1/').status_code, 404)
        self.client.force_login(self.admin)
        self.client.post(reverse('revogar', args=[self.pedido.pk]))
        self.client.logout()
        self.assertEqual(self.client.get(reverse('acompanhar', args=[self.pedido.token])).status_code, 404)

    def test_cancelar_exige_motivo_e_correcao_preserva_original(self):
        """Confere a justificativa obrigatória de cancelamento e a preservação do evento original após uma correção."""
        os = self.receber()
        with self.assertRaises(ValidationError):
            self.atualizar(os, 'cancelado', comentario='', user=self.admin)
        original = os.atividades.first()
        self.atualizar(os, comentario='Correção: recebido sem carregador', correcao_de=original.pk)
        original.refresh_from_db()
        self.assertIn('Com carregador', original.descricao)
        self.atualizar(os, 'cancelado', comentario='Cliente desistiu. Equipamento devolvido.', user=self.admin)

    def test_paginas_renderizam(self):
        """Confere respostas HTTP bem-sucedidas das páginas públicas e administrativas com os perfis apropriados."""
        os = self.receber()
        self.orcamento(os)
        for url in ['/', '/solicitar/', '/entrar/']:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.admin)
        for url in ['/painel/', '/painel/?q=Dell&atrasadas=1', '/painel/solicitacoes/', f'/painel/solicitacoes/{self.pedido.pk}/', f'/painel/os/{os.pk}/', '/painel/nova-os/', '/gestao/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_solicitacao_persiste_sem_os_e_reenvio(self):
        """Verifica que o formulário público persiste um único pedido no reenvio sem criar OS automaticamente."""
        response = self.client.get('/solicitar/')
        chave = response.context['form']['chave'].value()
        dados = {'chave': chave, 'nome': 'Ana Teste', 'telefone': '(11) 99999-2222', 'email': '', 'categoria': 'celular', 'marca': '', 'modelo': '', 'identificacao': '', 'servico': self.servico.pk, 'problema': 'Tela quebrada', 'confirmar': 'on'}
        self.assertEqual(self.client.post('/solicitar/', dados).status_code, 302)
        self.assertEqual(self.client.post('/solicitar/', dados).status_code, 302)
        self.assertEqual(Solicitacao.objects.filter(cliente__nome='Ana Teste').count(), 1)
        self.assertFalse(OrdemServico.objects.exists())

    def test_formularios_validam_valores_e_uploads(self):
        """Confere a rejeição de valores monetários inválidos e de arquivos que simulam imagens."""
        for itens in ['Peça; 0; 10', 'Peça; 1; NaN', 'Peça; 1; -1', 'Peça; 1; 1.001', 'inválido']:
            self.assertFalse(OrcamentoForm({'chave': uuid.uuid4(), 'itens': itens}).is_valid())
        self.assertTrue(OrcamentoForm({'chave': uuid.uuid4(), 'itens': 'Peça; 2; 10,50'}).is_valid())
        with self.assertRaises(ValidationError):
            validar_foto(SimpleUploadedFile('foto.jpg', b'<script>malicioso</script>', content_type='image/jpeg'))

    def test_csrf_exigido(self):
        """Verifica que o envio público sem token CSRF recebe resposta de acesso negado."""
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/solicitar/', {}).status_code, 403)

    def test_logs_ocultam_tokens_e_buscas_pessoais(self):
        """Confere que o filtro de logs remove tokens de acompanhamento e parâmetros com dados pessoais."""
        import logging
        from .logging import RedigirDados
        record = logging.LogRecord('django.server', logging.INFO, '', 1, 'GET %s', ('/acompanhar/token-secreto/?q=NomePessoal',), None)
        RedigirDados().filter(record)
        self.assertNotIn('token-secreto', record.getMessage())
        self.assertNotIn('NomePessoal', record.getMessage())

    def test_orcamento_http_idempotente(self):
        """Verifica que repetir o POST de orçamento com a mesma chave cria somente uma versão."""
        os = self.receber()
        self.client.force_login(self.tecnico)
        dados = {'acao': 'orcamento', 'chave': uuid.uuid4(), 'itens': 'Serviço; 1; 100,00'}
        url = reverse('ordem', args=[os.pk])
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.assertEqual(os.orcamentos.count(), 1)

    def test_anexos_privados_e_validacao_real(self):
        """Confere validação de imagens reais e truncadas e permissões de download de anexos privados e públicos."""
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as pasta, override_settings(MEDIA_ROOT=pasta):
            os = self.receber()
            content = BytesIO()
            Image.new('RGB', (8, 8), 'green').save(content, format='PNG')
            foto = SimpleUploadedFile('entrada.png', content.getvalue(), content_type='text/plain')
            foto = validar_foto(foto)
            services.anexar(self.pedido, foto, publico=False)
            anexo = Anexo.objects.latest('pk')
            url = reverse('anexo', args=[anexo.pk])
            self.assertEqual(self.client.get(url + '?token=' + self.pedido.token).status_code, 404)
            self.client.force_login(self.outro)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.tecnico)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')
            response.close()
            anexo.publico = True
            anexo.save()
            self.client.logout()
            response = self.client.get(url + '?token=' + self.pedido.token)
            self.assertEqual(response.status_code, 200)
            response.close()
            with self.assertRaises(ValidationError):
                validar_foto(SimpleUploadedFile('truncado.png', b'\x89PNG\r\n\x1a\ntruncado'))


from django.test import TransactionTestCase


class ConcorrenciaTest(TransactionTestCase):
    def test_recebimentos_simultaneos_geram_uma_os(self):
        """Executa dois recebimentos concorrentes e verifica a criação de uma única OS e um único evento de entrada."""
        from concurrent.futures import ThreadPoolExecutor
        from django.db import connections, OperationalError
        import time
        admin = get_user_model().objects.create_superuser('concorrencia', password='SenhaAleatoria!123')
        cliente = Cliente.objects.create(nome='Concorrência', telefone='11988887777')
        equipamento = Equipamento.objects.create(cliente=cliente, categoria='celular')
        pedido = Solicitacao.objects.create(cliente=cliente, equipamento=equipamento, problema='Teste')

        def converter():
            """Executa o recebimento em uma thread, repetindo bloqueios transitórios do banco em memória e fechando sua conexão ao terminar."""
            try:
                # Shared in-memory SQLite reports table locks immediately; a real file waits for timeout.
                for tentativa in range(20):
                    try:
                        return services.receber(pedido, {'recebido': True, 'recebimento': 'Entrada simultânea'}, admin).pk
                    except OperationalError as exc:
                        if 'locked' not in str(exc).lower() or tentativa == 19:
                            raise
                        time.sleep(0.02)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Cada chamada ignora o índice e dispara o mesmo recebimento em uma thread independente.
            resultados = list(executor.map(lambda _: converter(), range(2)))
        self.assertEqual(resultados[0], resultados[1])
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(Atividade.objects.count(), 1)
