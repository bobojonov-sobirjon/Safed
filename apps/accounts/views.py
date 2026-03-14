import random
import string
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from django.contrib.auth.models import Group

from .models import CustomUser, PhoneOTP, UserDevice
from .serializers import (
    CourierListSerializer,
    SendOTPSerializer,
    VerifyOTPSerializer,
    UserListSerializer,
    UserUpdateSerializer,
    UserUpdateByAdminSerializer,
    AdminLoginSerializer,
    AdminUpdateSerializer,
    UserProfileUpdateSerializer,
    StaffCreateSerializer,
    PasswordChangeByAdminSerializer,
    PasswordChangeByUserSerializer,
    UserDeviceSerializer,
    UserDeviceCreateSerializer,
    UserDeviceUpdateSerializer,
    UserDeviceActivateSerializer,
)
from .services.eskiz import send_sms


GROUP_USER = 'User'
GROUP_SUPER_ADMIN = 'Super Admin'
GROUP_ADMIN = 'Admin'
GROUP_OPERATOR = 'Operator'
GROUP_COURIER = 'Courier'
STAFF_GROUPS = [GROUP_SUPER_ADMIN, GROUP_ADMIN, GROUP_OPERATOR, GROUP_COURIER]


def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


def is_super_admin(user):
    return user_in_group(user, GROUP_SUPER_ADMIN)


def user_is_staff(user):
    return user.groups.filter(name__in=STAFF_GROUPS).exists()


def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# ========== Authorization (Rus) ==========

@extend_schema(
    tags=['Авторизация'],
    summary='Отправить SMS код',
    description='''Отправка OTP на указанный номер телефона.

**Примечание:** При DEBUG=True код возвращается в ответе.
''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'phone': {'type': 'string', 'description': 'Номер телефона', 'example': '998901234567'},
            },
            'required': ['phone'],
        }
    },
)
class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data['phone'].strip()
        code = generate_otp()

        PhoneOTP.objects.filter(phone=phone).delete()
        PhoneOTP.objects.create(phone=phone, code=code)
        message = f'Safed. Kod: {code}'
        result = send_sms(phone, message, code)
        if settings.DEBUG and not result.get('success'):
            return Response({
                'message': result.get('message', 'СМС не отправлено'),
                'code': code,
            }, status=status.HTTP_200_OK)
        if result.get('success'):
            return Response({'message': 'СМС код отправлен'}, status=status.HTTP_200_OK)
        return Response(
            {'message': result.get('message', 'Ошибка СМС'), 'code': result.get('code')},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    tags=['Авторизация'],
    summary='Проверить SMS код',
    description='''Проверка OTP кода.

**Поведение:**
- Если код верный и пользователь существует - возвращается JWT
- Если пользователя нет - создаётся новый и возвращается токен
''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'phone': {'type': 'string', 'description': 'Номер телефона', 'example': '998901234567'},
                'code': {'type': 'string', 'description': '6-значный код', 'example': '123456'},
            },
            'required': ['phone', 'code'],
        }
    },
)
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data['phone'].strip()
        code = serializer.validated_data['code'].strip()

        otp = PhoneOTP.objects.filter(phone=phone, code=code).order_by('-created_at').first()
        if not otp:
            return Response({'detail': 'Неверный код'}, status=status.HTTP_400_BAD_REQUEST)
        if otp.is_expired():
            return Response({'detail': 'Код истёк'}, status=status.HTTP_400_BAD_REQUEST)
        otp.is_verified = True
        otp.save()

        user = CustomUser.objects.filter(phone=phone).first()
        if not user:
            user = CustomUser.objects.create_user(phone=phone)
            user.is_verified = True
            user.save()
            user_group = Group.objects.filter(name=GROUP_USER).first()
            if user_group:
                user.groups.add(user_group)
        elif not user.groups.exists():
            user_group = Group.objects.filter(name=GROUP_USER).first()
            if user_group:
                user.groups.add(user_group)

        tokens = get_tokens_for_user(user)
        result = {
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': UserListSerializer(user).data,
        }
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Админ'],
    summary='Вход администратора',
    description='''Авторизация администратора по телефону и паролю.

**Доступные группы:** Super Admin, Admin, Operator, Courier
''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'phone': {'type': 'string', 'description': 'Номер телефона', 'example': '998901234567'},
                'password': {'type': 'string', 'description': 'Пароль', 'example': 'mypassword123'},
            },
            'required': ['phone', 'password'],
        }
    },
)
class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data['phone']
        password = serializer.validated_data['password']

        try:
            user = CustomUser.objects.get(phone=phone)
        except CustomUser.DoesNotExist:
            return Response({'detail': 'Неверные данные'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user_is_staff(user):
            return Response({'detail': 'Неверные данные'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.check_password(password):
            return Response({'detail': 'Неверные данные'}, status=status.HTTP_401_UNAUTHORIZED)

        tokens = get_tokens_for_user(user)
        result = {
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': UserListSerializer(user).data,
        }
        return Response(result)


@extend_schema(
    tags=['Админ'],
    summary='Обновить данные администратора',
    description='Изменение телефона и/или пароля текущего пользователя. Все поля опциональны.',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'phone': {'type': 'string', 'description': 'Новый номер телефона', 'example': '998901234568'},
                'password': {'type': 'string', 'description': 'Новый пароль', 'example': 'newpassword123'},
            },
        }
    },
)
class AdminUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        
        serializer = AdminUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        if 'phone' in v:
            user.phone = v['phone']
        if 'password' in v:
            user.set_password(v['password'])
        user.save()
        data = UserListSerializer(user).data
        return Response(data)


# ========== Users (Rus) ==========

@extend_schema(
    tags=['Пользователи'],
    summary='Мой профиль',
    description='Получить данные текущего пользователя.',
)
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = UserListSerializer(request.user).data
        return Response(data)


@extend_schema(
    tags=['Пользователи'],
    summary='Обновить мой профиль',
    description='Изменение имени и фамилии текущего пользователя. Все поля опциональны.',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'first_name': {'type': 'string', 'description': 'Имя', 'example': 'Иван'},
                'last_name': {'type': 'string', 'description': 'Фамилия', 'example': 'Иванов'},
            },
        }
    },
)
class UserProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = UserProfileUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        if 'first_name' in v:
            user.first_name = v['first_name']
        if 'last_name' in v:
            user.last_name = v['last_name']
        user.save()
        data = UserListSerializer(user).data
        return Response(data)

def _get_users_by_group(group_name):
    group = Group.objects.filter(name=group_name).first()
    if not group:
        return CustomUser.objects.none()
    return CustomUser.objects.filter(groups=group).order_by('-created_at')


def _filter_queryset_by_name_phone(queryset, first_name, last_name, phone):
    """Filter queryset by first_name, last_name, phone (icontains)."""
    if first_name:
        queryset = queryset.filter(first_name__icontains=first_name)
    if last_name:
        queryset = queryset.filter(last_name__icontains=last_name)
    if phone:
        queryset = queryset.filter(phone__icontains=phone)
    return queryset


# ========== Staff (Super Admin) — создание Admin, Operator, Courier ==========

@extend_schema(
    tags=['Персонал'],
    summary='Создать Admin / Operator / Courier',
    description='''Создание сотрудника. Только для Super Admin.

**Доступные группы:** Admin, Operator, Courier
''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'phone': {'type': 'string', 'description': 'Номер телефона', 'example': '998901234567'},
                'password': {'type': 'string', 'description': 'Пароль', 'example': 'staffpassword123'},
                'group': {'type': 'string', 'description': 'Группа', 'enum': ['Admin', 'Operator', 'Courier'], 'example': 'Operator'},
            },
            'required': ['phone', 'password', 'group'],
        }
    },
)
class StaffCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_super_admin(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        serializer = StaffCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        phone = v['phone'].strip()
        if CustomUser.objects.filter(phone=phone).exists():
            return Response({'phone': ['Номер уже занят']}, status=status.HTTP_400_BAD_REQUEST)
        user = CustomUser.objects.create_user(phone=phone, password=v['password'])
        user.is_verified = True
        user.is_admin = True
        user.save()
        group = Group.objects.get(name=v['group'])
        user.groups.add(group)
        result = UserListSerializer(user).data
        return Response(result, status=status.HTTP_201_CREATED)


# ========== Get all by group ==========

@extend_schema(
    tags=['Обычный пользователь'],
    summary='Список User (клиенты)',
    description='Только пользователи группы User. Pagination: limit, offset.',
    parameters=[
        OpenApiParameter(name='first_name', type=OpenApiTypes.STR),
        OpenApiParameter(name='last_name', type=OpenApiTypes.STR),
        OpenApiParameter(name='phone', type=OpenApiTypes.STR),
        OpenApiParameter(name='limit', type=OpenApiTypes.INT),
        OpenApiParameter(name='offset', type=OpenApiTypes.INT),
    ],
)
class UserGroupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        first_name = request.query_params.get('first_name', '').strip()
        last_name = request.query_params.get('last_name', '').strip()
        phone = request.query_params.get('phone', '').strip()

        queryset = _get_users_by_group(GROUP_USER)
        queryset = _filter_queryset_by_name_phone(queryset, first_name, last_name, phone)
        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = UserListSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


@extend_schema(
    tags=['Простой администратор'],
    summary='Список Admin',
    parameters=[
        OpenApiParameter(name='first_name', type=OpenApiTypes.STR),
        OpenApiParameter(name='last_name', type=OpenApiTypes.STR),
        OpenApiParameter(name='phone', type=OpenApiTypes.STR),
        OpenApiParameter(name='limit', type=OpenApiTypes.INT),
        OpenApiParameter(name='offset', type=OpenApiTypes.INT),
    ],
)
class AdminGroupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        queryset = _get_users_by_group(GROUP_ADMIN)
        first_name = request.query_params.get('first_name', '').strip()
        last_name = request.query_params.get('last_name', '').strip()
        phone = request.query_params.get('phone', '').strip()
        queryset = _filter_queryset_by_name_phone(queryset, first_name, last_name, phone)
        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = UserListSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


@extend_schema(
    tags=['Оператор'],
    summary='Список Operator',
    parameters=[
        OpenApiParameter(name='first_name', type=OpenApiTypes.STR),
        OpenApiParameter(name='last_name', type=OpenApiTypes.STR),
        OpenApiParameter(name='phone', type=OpenApiTypes.STR),
        OpenApiParameter(name='limit', type=OpenApiTypes.INT),
        OpenApiParameter(name='offset', type=OpenApiTypes.INT),
    ],
)
class OperatorGroupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        queryset = _get_users_by_group(GROUP_OPERATOR)
        first_name = request.query_params.get('first_name', '').strip()
        last_name = request.query_params.get('last_name', '').strip()
        phone = request.query_params.get('phone', '').strip()
        queryset = _filter_queryset_by_name_phone(queryset, first_name, last_name, phone)
        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = UserListSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


@extend_schema(
    tags=['Курьер'],
    summary='Список Courier',
    description='is_busy: true если у курьера есть заказ со статусом delivering в OrderCourier',
    parameters=[
        OpenApiParameter(name='first_name', type=OpenApiTypes.STR),
        OpenApiParameter(name='last_name', type=OpenApiTypes.STR),
        OpenApiParameter(name='phone', type=OpenApiTypes.STR),
        OpenApiParameter(name='limit', type=OpenApiTypes.INT),
        OpenApiParameter(name='offset', type=OpenApiTypes.INT),
    ],
)
class CourierGroupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        queryset = _get_users_by_group(GROUP_COURIER)
        first_name = request.query_params.get('first_name', '').strip()
        last_name = request.query_params.get('last_name', '').strip()
        phone = request.query_params.get('phone', '').strip()
        queryset = _filter_queryset_by_name_phone(queryset, first_name, last_name, phone)
        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = CourierListSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


# ========== Get by ID, PUT, DELETE ==========

@extend_schema(tags=['Персонал'], summary='Получить пользователя по ID')
class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            user = CustomUser.objects.get(pk=pk)
        except CustomUser.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if user_in_group(user, GROUP_USER) and not user_is_staff(request.user) and request.user != user:
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        return Response(UserListSerializer(user).data)


@extend_schema(
    tags=['Персонал'],
    summary='Обновить пользователя',
    description='Обновление данных пользователя администратором. Все поля опциональны.',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'first_name': {'type': 'string', 'description': 'Имя', 'example': 'Иван'},
                'last_name': {'type': 'string', 'description': 'Фамилия', 'example': 'Иванов'},
                'phone': {'type': 'string', 'description': 'Номер телефона', 'example': '998901234567'},
            },
        }
    },
)
class UserUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        user = CustomUser.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserUpdateByAdminSerializer(data=request.data, partial=True, context={'instance': user})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data
        for field in ['first_name', 'last_name', 'phone']:
            if field in v:
                setattr(user, field, v[field])
        user.save()
        return Response(UserListSerializer(user).data)


@extend_schema(tags=['Персонал'], summary='Удалить пользователя')
class UserDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not is_super_admin(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = CustomUser.objects.get(pk=pk)
        except CustomUser.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== PATCH password (admin) ==========

@extend_schema(
    tags=['Персонал'],
    summary='Сменить пароль (по id)',
    description='Смена пароля пользователя администратором.',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'password': {'type': 'string', 'description': 'Новый пароль', 'example': 'newpassword123'},
            },
            'required': ['password'],
        }
    },
)
class UserPasswordChangeByAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not user_is_staff(request.user):
            return Response({'detail': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PasswordChangeByAdminSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        password = serializer.validated_data['password']
        try:
            user = CustomUser.objects.get(pk=pk)
        except CustomUser.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        user.set_password(password)
        user.save()
        return Response({'detail': 'Пароль изменён'})


# ========== PATCH password (user self) — SMS verify ==========

@extend_schema(
    tags=['Пользователи'],
    summary='Отправить SMS для смены пароля',
    description='Отправляет код на телефон текущего пользователя. Если Eskiz не работает — код возвращается в ответе.',
)
class UserPasswordSendCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        phone = getattr(user, 'phone', None)
        if not phone:
            return Response({'detail': 'Телефон не указан'}, status=status.HTTP_400_BAD_REQUEST)

        code = generate_otp()

        PhoneOTP.objects.filter(phone=phone).delete()
        PhoneOTP.objects.create(phone=phone, code=code)
        message = f'Safed. Смена пароля. Код: {code}'
        result = send_sms(phone, message, code)
        if result.get('success'):
            return Response({'message': 'СМС код отправлен'}, status=status.HTTP_200_OK)
        return Response({
            'message': result.get('message', 'СМС не отправлено'),
            'code': result.get('code'),
            'detail': 'Используйте код для PATCH /users/me/password/',
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Пользователи'],
    summary='Сменить свой пароль',
    description='''Смена пароля после подтверждения SMS кодом.

**Порядок:**
1. Отправить запрос на `/api/users/me/password/send-code/`
2. Получить SMS код
3. Отправить `new_password` и `code`
''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'new_password': {'type': 'string', 'description': 'Новый пароль', 'example': 'mynewpassword123'},
                'code': {'type': 'string', 'description': 'SMS код', 'example': '123456'},
            },
            'required': ['new_password', 'code'],
        }
    },
)
class UserPasswordChangeByUserView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        serializer = PasswordChangeByUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone = getattr(user, 'phone', None)
        if not phone:
            return Response({'detail': 'Телефон не указан'}, status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data['code'].strip()
        new_password = serializer.validated_data['new_password']

        otp = PhoneOTP.objects.filter(phone=phone, code=code).order_by('-created_at').first()
        if not otp:
            return Response({'detail': 'Неверный код'}, status=status.HTTP_400_BAD_REQUEST)
        if otp.is_expired():
            return Response({'detail': 'Код истёк'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        otp.delete()
        return Response({'detail': 'Пароль изменён'})


# ========== UserDevice (Push notifications) ==========

@extend_schema_view(
    get=extend_schema(tags=['Устройства'], summary='Мои устройства'),
    post=extend_schema(
        tags=['Устройства'],
        summary='Добавить устройство',
        description='Регистрация устройства для push-уведомлений.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'device_token': {'type': 'string', 'description': 'FCM/APNs токен', 'example': 'fMd3sT7...'},
                    'device_type': {'type': 'string', 'description': 'Тип устройства', 'enum': ['android', 'ios'], 'example': 'android'},
                },
                'required': ['device_token', 'device_type'],
            }
        },
    ),
)
class UserDeviceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = UserDevice.objects.filter(user=request.user).order_by('-created_at')
        data = UserDeviceSerializer(devices, many=True).data
        return Response(data)

    def post(self, request):
        serializer = UserDeviceCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data

        device = UserDevice.objects.create(
            user=request.user,
            device_token=v['device_token'],
            device_type=v['device_type'],
        )
        data = UserDeviceSerializer(device).data
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Устройства'], summary='Устройство по ID')
class UserDeviceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            device = UserDevice.objects.get(pk=pk, user=request.user)
        except UserDevice.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserDeviceSerializer(device).data)


@extend_schema(
    tags=['Устройства'],
    summary='Обновить устройство',
    description='Обновление данных устройства. Все поля опциональны.',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'device_token': {'type': 'string', 'description': 'FCM/APNs токен', 'example': 'newToken...'},
                'device_type': {'type': 'string', 'enum': ['android', 'ios'], 'example': 'ios'},
            },
        }
    },
)
class UserDeviceUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        serializer = UserDeviceUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        v = serializer.validated_data

        try:
            device = UserDevice.objects.get(pk=pk, user=request.user)
        except UserDevice.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        if 'device_token' in v:
            device.device_token = v['device_token']
        if 'device_type' in v:
            device.device_type = v['device_type']
        device.save()
        return Response(UserDeviceSerializer(device).data)


@extend_schema(
    tags=['Устройства'],
    summary='Активировать/деактивировать',
    description='Включение или отключение push-уведомлений для устройства.',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'is_activate': {'type': 'boolean', 'description': 'Активировать устройство', 'example': True},
            },
            'required': ['is_activate'],
        }
    },
)
class UserDeviceActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = UserDeviceActivateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        is_activate = serializer.validated_data['is_activate']

        try:
            device = UserDevice.objects.get(pk=pk, user=request.user)
        except UserDevice.DoesNotExist:
            return Response({'detail': 'Не найден'}, status=status.HTTP_404_NOT_FOUND)
        device.is_activate = is_activate
        device.save()
        return Response(UserDeviceSerializer(device).data)

