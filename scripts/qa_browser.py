"""Smoke test real no Chrome local. Opcional: pip install playwright (não requer baixar navegador)."""
import os
import secrets
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coregestor.settings')
# Playwright sync runs an event loop internally; this single-threaded QA process owns its DB calls.
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
import django
django.setup()
from django.contrib.auth import get_user_model
from assistencia.models import Solicitacao, OrdemServico, Atividade, Anexo, Orcamento, ItemOrcamento
from playwright.sync_api import sync_playwright

base = 'http://127.0.0.1:8000'
password = secrets.token_urlsafe(20)
username = 'qa_' + secrets.token_hex(4)
user = get_user_model().objects.create_superuser(username, password=password)
pedido = None
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True, args=['--no-sandbox', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        # Guarda cada erro JavaScript do navegador para reprovar o teste ao final.
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base, wait_until='domcontentloaded')
        page.get_by_role('link', name='Solicitar serviço').first.click()
        page.get_by_label('Nome completo').fill('Cliente QA navegador')
        page.get_by_label('Telefone').fill('21988887777')
        page.get_by_role('button', name='Continuar').click()
        page.get_by_label('Categoria').select_option('celular')
        page.get_by_label('Marca (deixe vazio se não souber)').fill('Samsung')
        page.get_by_label('Modelo (opcional)').fill('QA Teste')
        page.get_by_role('button', name='Continuar').click()
        page.get_by_label('Descreva o problema').fill('Teste automatizado de navegador. Não liga.')
        page.get_by_label('Revisei os dados').check()
        page.get_by_role('button', name='Enviar solicitação').click()
        page.wait_for_url('**/acompanhar/**')
        public_url = page.url
        pedido = Solicitacao.objects.get(token=public_url.rstrip('/').split('/')[-1])
        assert not OrdemServico.objects.filter(solicitacao=pedido).exists()
        page.goto(base + '/entrar/')
        page.get_by_label('Usuário').fill(username)
        page.get_by_label('Senha').fill(password)
        page.get_by_role('button', name='Entrar no painel').click()
        page.wait_for_url('**/painel/')
        page.goto(base + f'/painel/solicitacoes/{pedido.pk}/')
        page.get_by_label('Confirmo o recebimento físico').check()
        page.get_by_label('Conferência:').fill('Sem avarias, recebido com carregador.')
        page.get_by_label('Técnico responsável').select_option(str(user.pk))
        page.get_by_role('button', name='Gerar OS').click()
        page.wait_for_url('**/painel/os/**')
        os_url = page.url

        def update(status='', note='Nota interna QA', delivery=False):
            """Preenche e envia uma atualização no navegador, aceita confirmações necessárias e verifica a ausência de erros no formulário."""
            form = page.locator('form:has(input[name=acao][value=atualizar])')
            form.get_by_label('Comentário / justificativa').fill(note)
            form.get_by_label('Alteração de status').select_option(status)
            if delivery:
                form.get_by_label('Confirmo que o equipamento foi entregue').check()
            # Aceita uma única confirmação de cancelamento ou entrega durante o teste automatizado.
            page.once('dialog', lambda dialog: dialog.accept()) if status in ('cancelado', 'finalizado') else None
            form.get_by_role('button', name='Salvar atualização').click()
            page.wait_for_load_state('domcontentloaded')
            assert not page.locator('.errorlist').count(), page.locator('.errorlist').all_text_contents()

        update('diagnostico')
        form = page.locator('form:has(input[name=acao][value=diagnostico])')
        form.get_by_label('Diagnóstico técnico').fill('Conector danificado.')
        form.get_by_role('button', name='Salvar diagnóstico').click()
        page.get_by_text('Criar nova versão do orçamento', exact=True).click()
        form = page.locator('form:has(input[name=acao][value=orcamento])')
        form.locator('textarea').fill('Reparo do conector; 1; 150,00')
        form.get_by_role('button', name='Salvar novo orçamento').click()
        update('aprovacao')
        page.get_by_text('Registrar decisão do cliente', exact=True).click()
        form = page.locator('form:has(input[name=acao][value=decisao])')
        form.locator('[name=decisao]').select_option('aprovado')
        form.get_by_label('Canal de contato').fill('Telefone')
        form.get_by_label('Observação da decisão').fill('Cliente aprovou orçamento de R$ 150,00.')
        form.get_by_role('button', name='Registrar decisão').click()
        for status in ['execucao', 'peca', 'execucao', 'testes', 'pronto']:
            update(status)
        update('finalizado', 'Entregue ao cliente.', True)
        assert OrdemServico.objects.get(solicitacao=pedido).status == 'finalizado'
        page.goto(base + '/painel/')
        page.screenshot(path=str(Path(tempfile.gettempdir()) / 'coregestor-painel.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(Path(tempfile.gettempdir()) / 'coregestor-painel-mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Overflow horizontal no painel mobile'
        page.goto(base)
        page.screenshot(path=str(Path(tempfile.gettempdir()) / 'coregestor-mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Overflow horizontal no catálogo mobile'
        page.goto(public_url)
        assert 'Nota interna QA' not in page.locator('main').inner_text()
        assert page.get_by_text('Finalizado', exact=True).count() == 1
        assert not errors, errors
        browser.close()
        print('OK: solicitação, login, recebimento, diagnóstico, orçamento, aprovação, peça, testes, entrega e mobile; sem erros JavaScript.')
finally:
    if pedido:
        ordem = OrdemServico.objects.filter(solicitacao=pedido).first()
        if ordem:
            Anexo.objects.filter(solicitacao=pedido).delete()
            Atividade.objects.filter(ordem=ordem).delete()
            ItemOrcamento.objects.filter(orcamento__ordem=ordem).delete()
            Orcamento.objects.filter(ordem=ordem).delete()
            ordem.delete()
        equipamento, cliente = pedido.equipamento, pedido.cliente
        pedido.delete()
        equipamento.delete()
        cliente.delete()
    user.delete()
