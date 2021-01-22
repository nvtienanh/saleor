from django.db import models


class Place(models.Model):
    name = models.CharField(max_length=256, blank=True)
    province = models.CharField(max_length=256, blank=True)
    place_type = models.CharField(max_length=256, blank=True)
    country = models.CharField(max_length=256, blank=True)
    hotels = models.IntegerField(default=0, blank=True)
    featured_image = models.CharField(max_length=256, blank=True)

    # objects = AddressQueryset.as_manager()

    class Meta:
        ordering = ("pk",)
        # app_label = "place"

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        class_ = type(self)
        return "<%s.%s(pk=%r, name=%r)>" % (
            class_.__module__,
            class_.__name__,
            self.pk,
            self.name,
        )
