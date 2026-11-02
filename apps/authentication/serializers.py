from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.functions import Lower, Trim
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import UserRole
from .permissions import user_role
from .selectors import ORDERING_FIELDS
from .services import create_operational_user

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = User.objects.filter(email__iexact=attrs['email'].strip()).first()
        if user is None:
            raise AuthenticationFailed('Credenciais inválidas.')
        user = authenticate(request=self.context.get('request'), username=user.get_username(), password=attrs['password'])
        if user is None or not user.is_active:
            raise AuthenticationFailed('Credenciais inválidas.')
        refresh = self.get_token(user)
        return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class CurrentUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'role')
        read_only_fields = fields
    def get_role(self, user) -> str | None:
        return user_role(user)


class AdminUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email', 'role',
            'is_active', 'is_superuser', 'date_joined',
        )
        read_only_fields = fields

    def get_role(self, user) -> str | None:
        return user_role(user)


class ExplicitFieldsSerializerMixin:
    allowed_input_fields: frozenset[str] = frozenset()

    def validate(self, attrs):
        submitted = set(self.initial_data)
        unexpected = sorted(submitted - self.allowed_input_fields)
        if unexpected:
            raise serializers.ValidationError({
                'non_field_errors': [f"Campos não permitidos: {', '.join(unexpected)}."],
            })
        if not submitted:
            raise serializers.ValidationError({'non_field_errors': ['Informe ao menos um campo.']})
        return attrs


class CurrentUserUpdateSerializer(ExplicitFieldsSerializerMixin, serializers.ModelSerializer):
    allowed_input_fields = frozenset(('first_name', 'last_name'))

    class Meta:
        model = User
        fields = ('first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'allow_blank': True, 'trim_whitespace': True},
            'last_name': {'allow_blank': True, 'trim_whitespace': True},
        }

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save(update_fields=list(validated_data))
        return instance


class PasswordChangeSerializer(ExplicitFieldsSerializerMixin, serializers.Serializer):
    allowed_input_fields = frozenset(('current_password', 'new_password', 'new_password_confirmation'))
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': ['Senha atual incorreta.']})
        if attrs['new_password'] != attrs['new_password_confirmation']:
            raise serializers.ValidationError({'new_password_confirmation': ['A confirmação da nova senha não confere.']})
        if user.check_password(attrs['new_password']):
            raise serializers.ValidationError({'new_password': ['A nova senha deve ser diferente da senha atual.']})
        try:
            validate_password(attrs['new_password'], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'new_password': list(error.messages)}) from error
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class OperationalUserCreateSerializer(serializers.ModelSerializer):
    allowed_input_fields = frozenset(('username', 'email', 'first_name', 'last_name', 'password'))
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    email = serializers.EmailField(required=True, allow_blank=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password')

    def validate(self, attrs):
        submitted = set(self.initial_data)
        unexpected = sorted(submitted - self.allowed_input_fields)
        if unexpected:
            raise serializers.ValidationError({
                'non_field_errors': [f"Campos não permitidos: {', '.join(unexpected)}."],
            })
        attrs['email'] = attrs['email'].strip().lower()
        duplicate = User.objects.annotate(
            normalized_email=Lower(Trim('email')),
        ).filter(normalized_email=attrs['email']).exists()
        if duplicate:
            raise serializers.ValidationError({'email': ['Já existe um usuário com este e-mail.']})
        candidate = User(
            username=attrs.get('username', ''),
            email=attrs['email'],
            first_name=attrs.get('first_name', ''),
            last_name=attrs.get('last_name', ''),
        )
        try:
            validate_password(attrs['password'], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': list(error.messages)}) from error
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        return create_operational_user(
            actor=request.user,
            request_id=request.request_id,
            **validated_data,
        )


class AdminUserUpdateSerializer(ExplicitFieldsSerializerMixin, serializers.Serializer):
    allowed_input_fields = frozenset(('first_name', 'last_name'))
    first_name = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True, max_length=150)


class AdminUserRoleSerializer(ExplicitFieldsSerializerMixin, serializers.Serializer):
    allowed_input_fields = frozenset(('role',))
    role = serializers.ChoiceField(choices=UserRole.choices)


class UserListFilterSerializer(ExplicitFieldsSerializerMixin, serializers.Serializer):
    allowed_input_fields = frozenset(('page', 'search', 'role', 'is_active', 'ordering'))
    page = serializers.IntegerField(required=False, min_value=1)
    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True, max_length=150)
    role = serializers.ChoiceField(required=False, choices=UserRole.choices)
    is_active = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(required=False, choices=tuple(ORDERING_FIELDS))

    def validate(self, attrs):
        submitted = set(self.initial_data)
        unexpected = sorted(submitted - self.allowed_input_fields)
        if unexpected:
            raise serializers.ValidationError({
                'non_field_errors': [f"Parâmetros não permitidos: {', '.join(unexpected)}."],
            })
        return attrs
