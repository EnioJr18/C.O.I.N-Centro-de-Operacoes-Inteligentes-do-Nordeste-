from django.conf import settings
from django.db import migrations, models
from django.db.models import Count, Q
import django.db.models.deletion


def validate_existing_missions(apps, schema_editor):
    Mission = apps.get_model('dispatch', 'Mission')
    in_progress = 'Em Andamento'

    missing_unit_ids = list(
        Mission.objects.filter(
            status=in_progress,
            assigned_unit__isnull=True,
        ).order_by('id').values_list('id', flat=True)
    )
    duplicate_units = list(
        Mission.objects.filter(
            status=in_progress,
            assigned_unit__isnull=False,
        )
        .values('assigned_unit_id')
        .annotate(mission_count=Count('id'))
        .filter(mission_count__gt=1)
        .order_by('assigned_unit_id')
    )
    duplicate_unit_ids = [row['assigned_unit_id'] for row in duplicate_units]
    duplicate_links = list(
        Mission.objects.filter(
            status=in_progress,
            assigned_unit_id__in=duplicate_unit_ids,
        )
        .order_by('assigned_unit_id', 'id')
        .values_list('assigned_unit_id', 'id')
    )

    if missing_unit_ids or duplicate_links:
        raise RuntimeError(
            'Integridade de missões inválida; nenhuma correção foi aplicada. '
            f'Missões em andamento sem unidade: {missing_unit_ids}. '
            'Vínculos duplicados (unit_id, mission_id): '
            f'{duplicate_links}.'
        )


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dispatch', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='missionhistory',
            name='actor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='mission_history_entries',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            validate_existing_missions,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='mission',
            constraint=models.CheckConstraint(
                condition=(
                    ~Q(status='Em Andamento')
                    | Q(assigned_unit__isnull=False)
                ),
                name='mission_active_requires_unit',
            ),
        ),
        migrations.AddConstraint(
            model_name='mission',
            constraint=models.UniqueConstraint(
                fields=('assigned_unit',),
                condition=Q(status='Em Andamento'),
                name='mission_one_active_per_unit',
            ),
        ),
    ]
