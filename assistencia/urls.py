from django.urls import path
from . import views

urlpatterns = [
    path('', views.catalogo, name='catalogo'),
    path('solicitar/', views.solicitar, name='solicitar'),
    path('acompanhar/<str:token>/', views.acompanhar, name='acompanhar'),
    path('painel/', views.painel, name='painel'),
    path('painel/solicitacoes/', views.solicitacoes, name='solicitacoes'),
    path('painel/solicitacoes/<int:pk>/', views.receber, name='receber'),
    path('painel/nova-os/', views.nova_os, name='nova_os'),
    path('painel/os/<int:pk>/', views.ordem, name='ordem'),
    path('painel/revogar/<int:pk>/', views.revogar, name='revogar'),
    path('anexos/<int:pk>/', views.anexo, name='anexo'),
]
