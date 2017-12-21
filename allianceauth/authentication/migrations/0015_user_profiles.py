# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-22 23:09
from __future__ import unicode_literals

import allianceauth.authentication.models
import django.db.models.deletion
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def create_guest_state(apps, schema_editor):
    State = apps.get_model('authentication', 'State')
    State.objects.update_or_create(name='Guest', defaults={'priority': 0, 'public': True})


def create_member_state(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    State = apps.get_model('authentication', 'State')
    EveAllianceInfo = apps.get_model('eveonline', 'EveAllianceInfo')
    EveCorporationInfo = apps.get_model('eveonline', 'EveCorporationInfo')

    member_state_name = getattr(settings, 'DEFAULT_AUTH_GROUP', 'Member')
    s = State.objects.update_or_create(name=member_state_name, defaults={'priority': 100, 'public': False})[0]
    try:
        # move group permissions to state
        g = Group.objects.get(name=member_state_name)
        [s.permissions.add(p.pk) for p in g.permissions.all()]
        g.delete()
    except Group.DoesNotExist:
        pass

    # auto-populate member IDs
    CORP_IDS = getattr(settings, 'CORP_IDS', [])
    ALLIANCE_IDS = getattr(settings, 'ALLIANCE_IDS', [])
    [s.member_corporations.add(c.pk) for c in EveCorporationInfo.objects.filter(corporation_id__in=CORP_IDS)]
    [s.member_alliances.add(a.pk) for a in EveAllianceInfo.objects.filter(alliance_id__in=ALLIANCE_IDS)]


def create_member_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    State = apps.get_model('authentication', 'State')
    member_state_name = getattr(settings, 'DEFAULT_AUTH_GROUP', 'Member')

    try:
        g = Group.objects.get(name=member_state_name)
        # move permissions back
        state = State.objects.get(name=member_state_name)
        [g.permissions.add(p.pk) for p in state.permissions.all()]

        # move users back
        for profile in state.userprofile_set.all().select_related('user'):
            profile.user.groups.add(g.pk)
    except (Group.DoesNotExist, State.DoesNotExist):
        pass


def create_blue_state(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    State = apps.get_model('authentication', 'State')
    EveAllianceInfo = apps.get_model('eveonline', 'EveAllianceInfo')
    EveCorporationInfo = apps.get_model('eveonline', 'EveCorporationInfo')
    blue_state_name = getattr(settings, 'DEFAULT_BLUE_GROUP', 'Blue')

    s = State.objects.update_or_create(name=blue_state_name, defaults={'priority': 50, 'public': False})[0]
    try:
        # move group permissions to state
        g = Group.objects.get(name=blue_state_name)
        [s.permissions.add(p.pk) for p in g.permissions.all()]
        g.permissions.clear()
    except Group.DoesNotExist:
        pass

    # auto-populate blue member IDs
    BLUE_CORP_IDS = getattr(settings, 'BLUE_CORP_IDS', [])
    BLUE_ALLIANCE_IDS = getattr(settings, 'BLUE_ALLIANCE_IDS', [])
    [s.member_corporations.add(c.pk) for c in EveCorporationInfo.objects.filter(corporation_id__in=BLUE_CORP_IDS)]
    [s.member_alliances.add(a.pk) for a in EveAllianceInfo.objects.filter(alliance_id__in=BLUE_ALLIANCE_IDS)]


def create_blue_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    State = apps.get_model('authentication', 'State')
    blue_state_name = getattr(settings, 'DEFAULT_BLUE_GROUP', 'Blue')

    try:
        g = Group.objects.get(name=blue_state_name)
        # move permissions back
        state = State.objects.get(name=blue_state_name)
        [g.permissions.add(p.pk) for p in state.permissions.all()]

        # move users back
        for profile in state.userprofile_set.all().select_related('user'):
            profile.user.groups.add(g.pk)
    except (Group.DoesNotExist, State.DoesNotExist):
        pass


def populate_ownerships(apps, schema_editor):
    Token = apps.get_model('esi', 'Token')
    CharacterOwnership = apps.get_model('authentication', 'CharacterOwnership')
    EveCharacter = apps.get_model('eveonline', 'EveCharacter')

    unique_character_owners = [t['character_id'] for t in
                               Token.objects.all().values('character_id').annotate(n=models.Count('user')) if
                               t['n'] == 1 and EveCharacter.objects.filter(character_id=t['character_id']).exists()]

    tokens = Token.objects.filter(character_id__in=unique_character_owners)
    for c_id in unique_character_owners:
        ts = tokens.filter(character_id=c_id).order_by('created')
        for t in ts:
            if t.can_refresh:
                # find newest refreshable token and use it as basis for CharacterOwnership
                CharacterOwnership.objecs.create_by_token(t)
                break


def create_profiles(apps, schema_editor):
    AuthServicesInfo = apps.get_model('authentication', 'AuthServicesInfo')
    State = apps.get_model('authentication', 'State')
    UserProfile = apps.get_model('authentication', 'UserProfile')
    EveCharacter = apps.get_model('eveonline', 'EveCharacter')

    # grab AuthServicesInfo if they have a unique main_char_id and the EveCharacter exists
    unique_mains = [auth['main_char_id'] for auth in
                    AuthServicesInfo.objects.exclude(main_char_id='').values('main_char_id').annotate(
                        n=models.Count('main_char_id')) if
                    auth['n'] == 1 and EveCharacter.objects.filter(character_id=auth['main_char_id']).exists()]

    auths = AuthServicesInfo.objects.filter(main_char_id__in=unique_mains).select_related('user')
    for auth in auths:
        # carry states and mains forward
        state = State.objects.get(name=auth.state if auth.state else 'Guest')
        char = EveCharacter.objects.get(character_id=auth.main_char_id)
        UserProfile.objects.create(user=auth.user, state=state, main_character=char)
    for auth in AuthServicesInfo.objects.exclude(main_char_id__in=unique_mains).select_related('user'):
        # prepare empty profiles
        state = State.objects.get(name='Guest')
        UserProfile.objects.create(user=auth.user, state=state)


def recreate_authservicesinfo(apps, schema_editor):
    AuthServicesInfo = apps.get_model('authentication', 'AuthServicesInfo')
    UserProfile = apps.get_model('authentication', 'UserProfile')
    User = apps.get_model('auth', 'User')

    # recreate all missing AuthServicesInfo models
    AuthServicesInfo.objects.bulk_create([AuthServicesInfo(user=u.pk) for u in User.objects.all()])

    # repopulate main characters
    for profile in UserProfile.objects.exclude(main_character__isnull=True).select_related('user', 'main_character'):
        AuthServicesInfo.objects.update_or_create(user=profile.user,
                                                  defaults={'main_char_id': profile.main_character.character_id})

    # repopulate states we understand
    for profile in UserProfile.objects.exclude(state__name='Guest').filter(
            state__name__in=['Member', 'Blue']).select_related('user', 'state'):
        AuthServicesInfo.objects.update_or_create(user=profile.user, defaults={'state': profile.state.name})


def disable_passwords(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    for u in User.objects.exclude(is_staff=True):
        # remove passwords for non-staff users to prevent password-based authentication
        # set_unusable_password is unavailable in migrations because :reasons:
        u.password = make_password(None)
        u.save()


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0008_alter_user_username_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('eveonline', '0008_remove_apikeys'),
        ('authentication', '0014_fleetup_permission'),
        ('esi', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CharacterOwnership',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('owner_hash', models.CharField(max_length=28, unique=True)),
                ('character', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='character_ownership', to='eveonline.EveCharacter')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='character_ownerships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'default_permissions': ('change', 'delete'),
                'ordering': ['user', 'character__character_name'],
            },
        ),
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=20, unique=True)),
                ('priority', models.IntegerField(help_text='Users get assigned the state with the highest priority available to them.', unique=True)),
                ('public', models.BooleanField(default=False, help_text='Make this state available to any character.')),
                ('member_alliances', models.ManyToManyField(blank=True, help_text='Alliances to whose members this state is available.', to='eveonline.EveAllianceInfo')),
                ('member_characters', models.ManyToManyField(blank=True, help_text='Characters to which this state is available.', to='eveonline.EveCharacter')),
                ('member_corporations', models.ManyToManyField(blank=True, help_text='Corporations to whose members this state is available.', to='eveonline.EveCorporationInfo')),
                ('permissions', models.ManyToManyField(blank=True, to='auth.Permission')),
            ],
            options={
                'default_permissions': ('change',),
                'ordering': ['-priority'],
            },
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('main_character', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='eveonline.EveCharacter')),
                ('state', models.ForeignKey(default=allianceauth.authentication.models.get_guest_state_pk, on_delete=django.db.models.deletion.SET_DEFAULT, to='authentication.State')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'default_permissions': ('change',),
            },
        ),
        migrations.RunPython(create_guest_state, migrations.RunPython.noop),
        migrations.RunPython(create_member_state, create_member_group),
        migrations.RunPython(create_blue_state, create_blue_group),
        migrations.RunPython(populate_ownerships, migrations.RunPython.noop),
        migrations.RunPython(create_profiles, recreate_authservicesinfo),
        migrations.RemoveField(
            model_name='authservicesinfo',
            name='user',
        ),
        migrations.DeleteModel(
            name='AuthServicesInfo',
        ),
        migrations.RunPython(disable_passwords, migrations.RunPython.noop),
        migrations.CreateModel(
            name='ProxyPermission',
            fields=[
            ],
            options={
                'proxy': True,
                'verbose_name': 'permission',
                'verbose_name_plural': 'permissions',
            },
            bases=('auth.permission',),
            managers=[
                ('objects', django.contrib.auth.models.PermissionManager()),
            ],
        ),
        migrations.CreateModel(
            name='ProxyUser',
            fields=[
            ],
            options={
                'proxy': True,
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
            },
            bases=('auth.user',),
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
