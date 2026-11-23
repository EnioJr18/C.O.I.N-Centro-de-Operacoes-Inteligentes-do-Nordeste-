from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fleet', '0002_alter_fleetunit_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FleetUnitHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('UNIT_CREATED', 'Unidade criada'), ('UNIT_UPDATED', 'Unidade atualizada'), ('UNIT_MAINTENANCE_STARTED', 'Manutenção iniciada'), ('UNIT_MAINTENANCE_ENDED', 'Manutenção encerrada')], max_length=32)),
                ('previous_status', models.CharField(blank=True, choices=[('AVAILABLE', 'Disponível'), ('BUSY', 'Em Atendimento'), ('MAINTENANCE', 'Em Manutenção')], max_length=20, null=True)),
                ('new_status', models.CharField(blank=True, choices=[('AVAILABLE', 'Disponível'), ('BUSY', 'Em Atendimento'), ('MAINTENANCE', 'Em Manutenção')], max_length=20, null=True)),
                ('changed_fields', models.JSONField(blank=True, default=list)),
                ('request_id', models.CharField(max_length=36)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='fleet_unit_history_entries', to=settings.AUTH_USER_MODEL)),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='history', to='fleet.fleetunit')),
            ],
            options={
                'ordering': ('-created_at', '-id'),
            },
        ),
        migrations.AddIndex(
            model_name='fleetunithistory',
            index=models.Index(fields=['unit', '-created_at', '-id'], name='fleet_history_unit_time_idx'),
        ),
    ]
