from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from .models import Servico, Configuracao


class AdministradorSomente(admin.ModelAdmin):
    def has_module_permission(self, request):
        """Exibe o módulo administrativo somente para superusuários."""
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        """Restringe consulta, cadastro e edição a superusuários; é reutilizado nas permissões de adicionar e alterar."""
        return request.user.is_superuser

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission

    def has_delete_permission(self, request, obj=None):
        """Impede exclusões pelo painel para preservar cadastros e vínculos históricos."""
        return False


@admin.register(Servico)
class ServicoAdmin(AdministradorSomente):
    list_display = ['nome', 'modalidade', 'valor', 'ativo']
    list_filter = ['ativo', 'modalidade']
    search_fields = ['nome']


@admin.register(Configuracao)
class ConfiguracaoAdmin(AdministradorSomente):
    def has_add_permission(self, request):
        """Permite cadastrar a identidade da assistência somente se o administrador ainda não criou uma configuração."""
        return request.user.is_superuser and not Configuracao.objects.exists()


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class FuncionarioAdmin(UserAdmin):
    def has_module_permission(self, request):
        """Exibe o módulo de funcionários somente para superusuários."""
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        """Restringe consulta, criação e edição de funcionários a superusuários, inclusive pelas permissões reutilizadas."""
        return request.user.is_superuser

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission

    def has_delete_permission(self, request, obj=None):
        """Impede excluir funcionários pelo painel; a desativação preserva o histórico de autoria."""
        return False


admin.site.site_header = 'CoreGestor • Configurações'
admin.site.site_title = 'CoreGestor'
admin.site.index_title = 'Serviços, equipe e identidade'
