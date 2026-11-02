from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from .models import (
    UserAdministrationAction,
    UserAdministrationEvent,
    UserProfile,
    UserRole,
)
from .permissions import user_role


User = get_user_model()
LAST_ADMIN_MESSAGE = 'Não é possível remover o último administrador ativo do sistema.'
SELF_MANAGEMENT_MESSAGE = 'Use a área de perfil para administrar sua própria conta.'
SUPERUSER_MESSAGE = 'Superusuários são somente leitura nesta API.'
ADMIN_PERMISSION_MESSAGE = 'Seu usuário não possui autorização administrativa.'


class UserAdministrationConflictError(Exception):
    pass


class UserAdministrationForbiddenError(Exception):
    pass


class UserProfileMissingError(Exception):
    pass


def _event(*, actor, target, action, request_id, **changes):
    return UserAdministrationEvent.objects.create(
        actor=actor,
        target=target,
        action=action,
        request_id=request_id,
        **changes,
    )


def _ensure_mutable(actor, target):
    if actor.pk == target.pk:
        raise UserAdministrationForbiddenError(SELF_MANAGEMENT_MESSAGE)
    if target.is_superuser:
        raise UserAdministrationForbiddenError(SUPERUSER_MESSAGE)


def _lock_and_validate_actor(actor_id):
    actor = User.objects.select_for_update().get(pk=actor_id)
    if not actor.is_active:
        raise UserAdministrationForbiddenError(ADMIN_PERMISSION_MESSAGE)
    if not actor.is_superuser:
        try:
            profile = UserProfile.objects.select_for_update().get(user=actor)
        except UserProfile.DoesNotExist as error:
            raise UserAdministrationForbiddenError(ADMIN_PERMISSION_MESSAGE) from error
        if profile.role != UserRole.ADMIN:
            raise UserAdministrationForbiddenError(ADMIN_PERMISSION_MESSAGE)
    return actor


def _lock_administrator_set():
    """Serializes every mutation that can change the active administrator set."""
    profile_user_ids = list(
        UserProfile.objects.select_for_update()
        .filter(role=UserRole.ADMIN)
        .order_by('user_id')
        .values_list('user_id', flat=True)
    )
    superuser_ids = list(
        User.objects.filter(is_superuser=True)
        .order_by('id')
        .values_list('id', flat=True)
    )
    administrator_ids = sorted(set(profile_user_ids) | set(superuser_ids))
    if administrator_ids:
        list(
            User.objects.select_for_update()
            .filter(pk__in=administrator_ids)
            .order_by('id')
            .values_list('id', flat=True)
        )


def _active_administrator_count():
    return (
        User.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(profile__role=UserRole.ADMIN))
        .distinct()
        .count()
    )


@transaction.atomic
def create_operational_user(*, actor, request_id, **validated_data):
    _lock_administrator_set()
    actor = _lock_and_validate_actor(actor.pk)
    password = validated_data.pop('password')
    user = User.objects.create_user(password=password, is_active=True, **validated_data)
    _event(
        actor=actor,
        target=user,
        action=UserAdministrationAction.USER_CREATED,
        request_id=request_id,
        new_role=UserRole.OPERADOR,
        new_is_active=True,
    )
    return user


@transaction.atomic
def update_managed_user(*, actor, target_id, values, request_id):
    _lock_administrator_set()
    locked_users = list(
        User.objects.select_for_update()
        .filter(pk__in=sorted((actor.pk, target_id)))
        .order_by('pk')
    )
    users_by_id = {user.pk: user for user in locked_users}
    actor = users_by_id.get(actor.pk)
    target = users_by_id.get(target_id)
    if actor is None or target is None:
        raise User.DoesNotExist
    if not actor.is_active:
        raise UserAdministrationForbiddenError(ADMIN_PERMISSION_MESSAGE)
    if not actor.is_superuser:
        try:
            actor_profile = UserProfile.objects.select_for_update().get(user=actor)
        except UserProfile.DoesNotExist as error:
            raise UserAdministrationForbiddenError(ADMIN_PERMISSION_MESSAGE) from error
        if actor_profile.role != UserRole.ADMIN:
            raise UserAdministrationForbiddenError(ADMIN_PERMISSION_MESSAGE)
    _ensure_mutable(actor, target)
    changed_fields = [field for field, value in values.items() if getattr(target, field) != value]
    if not changed_fields:
        return target
    for field in changed_fields:
        setattr(target, field, values[field])
    target.save(update_fields=changed_fields)
    _event(
        actor=actor,
        target=target,
        action=UserAdministrationAction.PROFILE_UPDATED,
        request_id=request_id,
        changed_fields=changed_fields,
    )
    return target


@transaction.atomic
def change_user_role(*, actor, target_id, new_role, request_id):
    _lock_administrator_set()
    target = User.objects.select_for_update().get(pk=target_id)
    _ensure_mutable(actor, target)
    try:
        profile = UserProfile.objects.select_for_update().get(user=target)
    except UserProfile.DoesNotExist as error:
        raise UserProfileMissingError('O usuário não possui perfil operacional.') from error
    previous_role = profile.role
    if previous_role == new_role:
        _lock_and_validate_actor(actor.pk)
        return target
    if previous_role == UserRole.ADMIN and target.is_active and _active_administrator_count() <= 1:
        raise UserAdministrationConflictError(LAST_ADMIN_MESSAGE)
    actor = _lock_and_validate_actor(actor.pk)
    profile.role = new_role
    profile.save(update_fields=['role'])
    _event(
        actor=actor,
        target=target,
        action=UserAdministrationAction.ROLE_CHANGED,
        request_id=request_id,
        previous_role=previous_role,
        new_role=new_role,
    )
    target.profile = profile
    return target


@transaction.atomic
def set_user_active(*, actor, target_id, is_active, request_id):
    _lock_administrator_set()
    target = User.objects.select_for_update().get(pk=target_id)
    _ensure_mutable(actor, target)
    previous = target.is_active
    if previous == is_active:
        _lock_and_validate_actor(actor.pk)
        return target
    if not is_active and user_role(target) == UserRole.ADMIN and _active_administrator_count() <= 1:
        raise UserAdministrationConflictError(LAST_ADMIN_MESSAGE)
    actor = _lock_and_validate_actor(actor.pk)
    target.is_active = is_active
    target.save(update_fields=['is_active'])
    _event(
        actor=actor,
        target=target,
        action=(
            UserAdministrationAction.USER_ACTIVATED
            if is_active
            else UserAdministrationAction.USER_DEACTIVATED
        ),
        request_id=request_id,
        previous_is_active=previous,
        new_is_active=is_active,
    )
    return target
