# Generated by Django 2.0.4 on 2018-04-14 18:28

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_initial_records(apps, schema_editor):
    OwnershipRecord = apps.get_model('authentication', 'OwnershipRecord')
    CharacterOwnership = apps.get_model('authentication', 'CharacterOwnership')

    OwnershipRecord.objects.bulk_create([
        OwnershipRecord(user=o.user, character=o.character, owner_hash=o.owner_hash) for o in CharacterOwnership.objects.all()
    ])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('eveonline', '0009_on_delete'),
        ('authentication', '0015_user_profiles'),
    ]

    operations = [
        migrations.CreateModel(
            name='OwnershipRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('owner_hash', models.CharField(db_index=True, max_length=28)),
                ('created', models.DateTimeField(auto_now=True)),
                ('character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ownership_records', to='eveonline.EveCharacter')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ownership_records', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created'],
            },
        ),
        migrations.RunPython(create_initial_records, migrations.RunPython.noop)
    ]
