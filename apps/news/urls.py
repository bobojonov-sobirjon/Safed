from django.urls import path
from . import views

urlpatterns = [
    # Posts
    path('posts/', views.PostListView.as_view(), name='post-list'),
    path('posts/<int:pk>/', views.PostDetailView.as_view(), name='post-detail'),
    path('posts/create/', views.PostCreateView.as_view(), name='post-create'),
    path('posts/<int:pk>/update/', views.PostUpdateView.as_view(), name='post-update'),
    path('posts/<int:pk>/delete/', views.PostDeleteView.as_view(), name='post-delete'),

    # PostImages
    path('post-images/', views.PostImageListView.as_view(), name='post-image-list'),
    path('post-images/<int:pk>/', views.PostImageDetailView.as_view(), name='post-image-detail'),
    path('post-images/create/', views.PostImageCreateView.as_view(), name='post-image-create'),
    path('post-images/<int:pk>/update/', views.PostImageUpdateView.as_view(), name='post-image-update'),
    path('post-images/<int:pk>/delete/', views.PostImageDeleteView.as_view(), name='post-image-delete'),
]
