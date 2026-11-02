import shutil
import sqlite3
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Backup consistente do SQLite e cópia dos anexos privados (pause uploads durante a cópia).'

    def add_arguments(self, parser):
        """Declara o argumento obrigatório com o diretório de destino do backup."""
        parser.add_argument('destino', help='Diretório novo para guardar o backup')

    def handle(self, *args, **options):
        """Cria um backup do SQLite e copia os anexos privados para uma pasta nova.
        
        Rejeita destinos existentes ou dentro dos anexos, usa a API de backup do SQLite
        e grava um manifesto com a data UTC. Uploads devem ser pausados durante a cópia
        para manter o conjunto de banco e arquivos consistente."""
        destino = Path(options['destino']).resolve()
        origem = Path(settings.DATABASES['default']['NAME']).resolve()
        media = Path(settings.MEDIA_ROOT).resolve()
        if destino.exists():
            raise CommandError('Use um diretório novo para não sobrescrever um backup existente.')
        if destino == media or media in destino.parents:
            raise CommandError('O backup não pode ficar dentro da pasta de anexos.')
        destino.mkdir(parents=True)
        with sqlite3.connect(origem) as source, sqlite3.connect(destino / 'db.sqlite3') as target:
            source.backup(target)
        if media.exists():
            shutil.copytree(media, destino / 'private_uploads')
        (destino / 'manifesto.txt').write_text(f'CoreGestor\nBackup UTC: {timezone.now().isoformat()}\nRestaure banco e anexos em conjunto. A chave secreta deve ser guardada separadamente.\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Backup concluído: {destino}'))
