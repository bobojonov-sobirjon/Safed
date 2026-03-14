from django.urls import path
from . import views

urlpatterns = [
    # Authorization
    path('auth/login/', views.SendOTPView.as_view(), name='send-otp'),
    path('auth/verify-otp/', views.VerifyOTPView.as_view(), name='verify-otp'),

    # Admin / Staff login
    path('auth/admin-login/', views.AdminLoginView.as_view(), name='admin-login'),
    path('auth/admin/update/', views.AdminUpdateView.as_view(), name='admin-update'),

    # Profile (request.user)
    path('users/me/', views.UserProfileView.as_view(), name='user-profile'),
    path('users/me/update/', views.UserProfileUpdateView.as_view(), name='user-profile-update'),
    path('users/me/password/send-code/', views.UserPasswordSendCodeView.as_view(), name='user-password-send-code'),
    path('users/me/password/', views.UserPasswordChangeByUserView.as_view(), name='user-password-change'),

    # Staff create (Super Admin only)
    path('staff/create/', views.StaffCreateView.as_view(), name='staff-create'),

    # Get all by group
    path('users/group/users/', views.UserGroupListView.as_view(), name='users-list'),
    path('staff/admins/', views.AdminGroupListView.as_view(), name='admins-list'),
    path('staff/operators/', views.OperatorGroupListView.as_view(), name='operators-list'),
    path('staff/couriers/', views.CourierGroupListView.as_view(), name='couriers-list'),

    # User by ID
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
    path('users/<int:pk>/update/', views.UserUpdateView.as_view(), name='user-update'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user-delete'),
    path('users/<int:pk>/password/', views.UserPasswordChangeByAdminView.as_view(), name='user-password-change-admin'),

    # UserDevice (Push notifications)
    path('devices/', views.UserDeviceListCreateView.as_view(), name='device-list-create'),
    path('devices/<int:pk>/', views.UserDeviceDetailView.as_view(), name='device-detail'),
    path('devices/<int:pk>/update/', views.UserDeviceUpdateView.as_view(), name='device-update'),
    path('devices/<int:pk>/activate/', views.UserDeviceActivateView.as_view(), name='device-activate'),
]
