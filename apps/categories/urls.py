from django.urls import path
from . import views

urlpatterns = [
    path('categories/', views.CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/child/', views.ChildCategoryCreateView.as_view(), name='category-child-create'),
    path('categories/<int:pk>/', views.CategoryDetailUpdateDeleteView.as_view(), name='category-detail'),
]
