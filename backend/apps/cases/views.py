from django.db.models import Q
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework import status
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.users.authentication import AccountKitUserAuthentication
from apps.arranges.models import Arrange
from .serializers import (
    CaseWriteSerializer,
    CaseSerializer,
    CaseRetrieveSerializer,
    TypeSerializer,
    RegionSerializer,
    VuetableParamsExpectations,
)
from .models import (
    Type,
    Region,
    Case,
    State,
)
from .schemas import vuetable_schema


class RegionViewSet(ReadOnlyModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    permission_classes = []
    http_method_names = ['get']


class TypeViewSet(ReadOnlyModelViewSet):
    queryset = Type.objects.all()
    serializer_class = TypeSerializer
    permission_classes = []
    http_method_names = ['get']


class CaseViewSet(ModelViewSet):
    queryset = Case.objects.exclude(state='draft')
    serializer_class = CaseSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ['get', 'post', 'retrieve']
    pagination_class = LimitOffsetPagination
    filter_backends = (OrderingFilter, SearchFilter)
    search_fields = ('id', 'number', 'type__name', 'location', 'title', 'content',
                     'disapprove_info', 'arranges__title', 'arranges__content')
    ordering_fields = ('id', 'number', 'type')

    def get_serializer_class(self):
        if self.action in ['create', 'update']:
            return CaseWriteSerializer
        if self.action == 'retrieve':
            return CaseRetrieveSerializer
        return CaseSerializer

    def get_authenticators(self):
        if self.request.method == "POST":
            self.authentication_classes = [AccountKitUserAuthentication]
        return [auth() for auth in self.authentication_classes]

    def perform_create(self, serializer):
        """Create時透過jwt user token，從user instance取得mobile"""
        user = self.request.user
        serializer.validated_data['mobile'] = user.mobile
        serializer.save()

    @action(methods=['GET'], detail=False, schema=vuetable_schema)
    def vuetable(self, request):
        queryset = self.queryset

        qpe = VuetableParamsExpectations(data=request.query_params)
        if not qpe.is_valid():
            return Response(
                data=qpe.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        query = qpe.validated_data['query']
        ascending = qpe.validated_data['ascending']
        sort = qpe.validated_data['sort']
        page = qpe.validated_data['page'] - 1
        limit = qpe.validated_data['limit']

        if ascending == 'desc':
            sort = '-' + sort

        for state, title in State.CHOICES:
            if query == title:
                query = state

        if query:
            arrange_ids = Arrange.objects.filter(Q(title__icontains=query)
                                                 | Q(content__icontains=query)).values_list('id', flat=True)

            queryset = queryset.filter(Q(number__icontains=query)
                                       | Q(title__icontains=query)
                                       | Q(content__icontains=query)
                                       | Q(location__icontains=query)
                                       | Q(type__name__icontains=query)
                                       | Q(state__icontains=query)
                                       | Q(disapprove_info__icontains=query)
                                       | Q(arranges__id__in=arrange_ids)).distinct()

        count = queryset.count()
        start = limit * page
        queryset = queryset.order_by(sort)[start:start+limit]

        serializer = self.serializer_class(queryset, many=True)
        result = {
            'data': serializer.data,
            'count': count,
        }
        return Response(result, status=status.HTTP_200_OK)
