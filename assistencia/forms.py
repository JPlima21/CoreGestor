import re
import uuid
import warnings
from PIL import Image, UnidentifiedImageError
from django import forms
from django.contrib.auth import get_user_model
from .models import Equipamento, Servico, OrdemServico, Solicitacao


class SolicitarForm(forms.Form):
    chave = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    nome = forms.CharField(label='Nome completo', max_length=120)
    telefone = forms.CharField(max_length=25)
    email = forms.EmailField(label='E-mail (opcional)', required=False)
    categoria = forms.ChoiceField(choices=Equipamento.CATEGORIAS)
    marca = forms.CharField(label='Marca (deixe vazio se não souber)', max_length=80, required=False)
    modelo = forms.CharField(label='Modelo (opcional)', max_length=100, required=False)
    identificacao = forms.CharField(label='Série / IMEI (opcional)', max_length=100, required=False)
    servico = forms.ModelChoiceField(label='Serviço', queryset=Servico.objects.filter(ativo=True), required=False, empty_label='Não sei qual é o problema')
    problema = forms.CharField(label='Descreva o problema e suas observações', widget=forms.Textarea)
    foto = forms.FileField(label='Foto opcional (JPEG, PNG ou WebP, até 5 MB)', required=False)
    confirmar = forms.BooleanField(label='Revisei os dados e confirmo o envio')

    def clean_telefone(self):
        """Remove a formatação do telefone e exige de 10 a 15 dígitos, incluindo DDD."""
        value = re.sub(r'\D', '', self.cleaned_data['telefone'])
        if not 10 <= len(value) <= 15:
            raise forms.ValidationError('Informe um telefone com DDD válido.')
        return value

    def clean_foto(self):
        """Valida a foto opcional enviada pelo cliente antes de criar a solicitação."""
        return validar_foto(self.cleaned_data.get('foto'))


def validar_foto(f):
    """Valida uma imagem opcional e retorna o arquivo pronto para armazenamento.
    
    Limita o upload a 5 MB e 25 megapixels, verifica JPEG, PNG ou WebP com Pillow,
    rejeita conteúdo inválido e define o tipo MIME a partir do conteúdo real.
    Retorna None quando não há arquivo e lança ValidationError em caso de falha."""
    if not f:
        return None
    if f.size > 5 * 1024 * 1024:
        raise forms.ValidationError('O arquivo deve ter até 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(f)
            if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 25_000_000:
                raise ValueError
            tipo = Image.MIME[image.format]
            image.verify()
        f.seek(0)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise forms.ValidationError('Envie uma imagem JPEG, PNG ou WebP válida.')
    f.content_type = tipo
    return f


class ReceberForm(forms.Form):
    recebido = forms.BooleanField(label='Confirmo o recebimento físico do equipamento')
    recebimento = forms.CharField(label='Conferência: defeito, estado de conservação e acessórios', widget=forms.Textarea)
    tecnico = forms.ModelChoiceField(label='Técnico responsável', queryset=get_user_model().objects.filter(is_active=True), required=False)
    previsao = forms.DateField(label='Previsão de entrega', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    identificacao = forms.CharField(label='Número de série / IMEI', max_length=100, required=False)
    foto = forms.FileField(label='Foto de entrada (opcional)', required=False)

    def clean_foto(self):
        """Aplica a validação de imagens à foto de entrada do equipamento."""
        return validar_foto(self.cleaned_data.get('foto'))


class AtualizarForm(forms.Form):
    chave = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    versao = forms.IntegerField(widget=forms.HiddenInput)
    comentario = forms.CharField(label='Comentário / justificativa', widget=forms.Textarea, required=False)
    status = forms.ChoiceField(label='Alteração de status', choices=[('', 'Manter status atual')] + OrdemServico.STATUS, required=False)
    publico = forms.BooleanField(label='Visível para o cliente (padrão: nota interna)', required=False)
    entrega = forms.BooleanField(label='Confirmo que o equipamento foi entregue ao cliente', required=False)
    correcao_de = forms.IntegerField(label='ID do evento corrigido (opcional)', required=False, min_value=1)
    foto = forms.FileField(label='Anexar foto', required=False)

    def clean_foto(self):
        """Aplica a validação de imagens à foto anexada a uma atualização da OS."""
        return validar_foto(self.cleaned_data.get('foto'))


class OperacaoForm(forms.Form):
    chave = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)


class DiagnosticoForm(OperacaoForm):
    diagnostico = forms.CharField(label='Diagnóstico técnico', widget=forms.Textarea)


class OrcamentoForm(OperacaoForm):
    itens = forms.CharField(label='Itens: uma linha por item, no formato descrição; quantidade; valor unitário', widget=forms.Textarea(attrs={'placeholder': 'Limpeza preventiva; 1; 120,00\nMemória RAM; 2; 180,00'}))

    def clean_itens(self):
        """Converte as linhas do orçamento em tuplas de descrição, quantidade e valor Decimal.
        
        Exige o formato descrição; quantidade; valor, de 1 a 100 itens, quantidades
        inteiras positivas e valores finitos não negativos com até duas casas decimais.
        Lança ValidationError quando uma linha ou quantidade de itens é inválida."""
        from decimal import Decimal, InvalidOperation
        items = []
        for line in self.cleaned_data['itens'].splitlines():
            try:
                descricao, quantidade, valor = [s.strip() for s in line.split(';')]
                quantidade, valor = int(quantidade), Decimal(valor.replace(',', '.'))
                if not descricao or len(descricao) > 200 or not 1 <= quantidade <= 1000 or not valor.is_finite() or not 0 <= valor <= Decimal('99999999.99') or valor.as_tuple().exponent < -2:
                    raise ValueError
                items.append((descricao, quantidade, valor))
            except (ValueError, InvalidOperation):
                raise forms.ValidationError('Use descrição; quantidade inteira positiva; valor com até duas casas decimais em cada linha.')
        if not items or len(items) > 100:
            raise forms.ValidationError('Informe de 1 a 100 itens.')
        return items


class DecisaoForm(OperacaoForm):
    decisao = forms.ChoiceField(label='Decisão', choices=[('aprovado', 'Aprovado'), ('recusado', 'Recusado')])
    canal = forms.CharField(label='Canal de contato', max_length=80)
    observacao = forms.CharField(label='Observação da decisão do cliente', widget=forms.Textarea)


class SituacaoForm(forms.Form):
    situacao = forms.ChoiceField(choices=Solicitacao.SITUACOES[:3] + [Solicitacao.SITUACOES[-1]])


class AtribuirForm(OperacaoForm):
    tecnico = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True), required=False)
    previsao = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
