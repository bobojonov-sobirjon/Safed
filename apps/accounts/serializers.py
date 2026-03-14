from rest_framework import serializers
from .models import CustomUser, UserDevice


_REQUIRED = {'required': 'Обязательное поле.'}

class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True, max_length=20, error_messages=_REQUIRED)


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True, error_messages=_REQUIRED)
    code = serializers.CharField(required=True, max_length=6, error_messages=_REQUIRED)


class UserListSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'phone', 'is_active', 'groups', 'created_at']

    def get_groups(self, obj):
        return list(obj.groups.values_list('name', flat=True))


class CourierListSerializer(UserListSerializer):
    """Courier uchun — is_busy: OrderCourier da status=delivering order bor-yo'q"""
    is_busy = serializers.SerializerMethodField()

    class Meta(UserListSerializer.Meta):
        fields = ['id', 'first_name', 'last_name', 'phone', 'is_active', 'groups', 'is_busy', 'created_at']

    def get_is_busy(self, obj):
        from apps.orders.models import OrderCourier
        return OrderCourier.objects.filter(courier=obj, order__status='delivering').exists()


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone']

    def validate_phone(self, value):
        if value and self.instance:
            if CustomUser.objects.filter(phone=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError('Номер уже занят')
        return value


class AdminLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True, error_messages=_REQUIRED)
    password = serializers.CharField(required=True, write_only=True, error_messages=_REQUIRED)


class AdminUpdateSerializer(serializers.Serializer):
    """Только phone и password для администратора"""
    phone = serializers.CharField(required=False)
    password = serializers.CharField(required=False, write_only=True)


class UserProfileUpdateSerializer(serializers.Serializer):
    """Только first_name, last_name для текущего пользователя"""
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)


class StaffCreateSerializer(serializers.Serializer):
    """Создание Admin, Operator, Courier (только Super Admin)"""
    phone = serializers.CharField(required=True, error_messages=_REQUIRED)
    password = serializers.CharField(required=True, write_only=True, error_messages=_REQUIRED)
    group = serializers.ChoiceField(
        choices=[('Admin', 'Admin'), ('Operator', 'Operator'), ('Courier', 'Courier')],
        required=True,
        error_messages=_REQUIRED,
    )
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)


class UserUpdateByAdminSerializer(serializers.Serializer):
    """Обновление пользователя (first_name, last_name, phone)"""
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False)

    def validate_phone(self, value):
        if value and self.context.get('instance'):
            if CustomUser.objects.filter(phone=value).exclude(pk=self.context['instance'].pk).exists():
                raise serializers.ValidationError('Номер уже занят')
        return value


class PasswordChangeByAdminSerializer(serializers.Serializer):
    """Смена пароля администратором (по id)"""
    password = serializers.CharField(required=True, write_only=True, error_messages=_REQUIRED)


class PasswordChangeByUserSerializer(serializers.Serializer):
    """Смена пароля пользователем (request.user) — после проверки SMS"""
    new_password = serializers.CharField(required=True, write_only=True, error_messages=_REQUIRED)
    code = serializers.CharField(required=True, error_messages=_REQUIRED)


# ========== UserDevice (Push notifications) ==========

class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = ['id', 'user', 'device_token', 'device_type', 'is_activate', 'created_at', 'updated_at']
        read_only_fields = ['user', 'created_at', 'updated_at']


class UserDeviceCreateSerializer(serializers.Serializer):
    device_token = serializers.CharField(required=True, max_length=512, error_messages=_REQUIRED)
    device_type = serializers.CharField(required=True, max_length=50, error_messages=_REQUIRED)


class UserDeviceUpdateSerializer(serializers.Serializer):
    device_token = serializers.CharField(required=False, max_length=512)
    device_type = serializers.CharField(required=False, max_length=50)


class UserDeviceActivateSerializer(serializers.Serializer):
    is_activate = serializers.BooleanField(required=True)
