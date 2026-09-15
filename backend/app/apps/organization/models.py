from django.db import models


class Building(models.Model):
    """楼栋。"""

    code = models.CharField('楼栋编号', max_length=40, unique=True)
    name = models.CharField('楼栋名称', max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'org_building'
        ordering = ['code']

    def __str__(self):
        return self.name


class Area(models.Model):
    """巡检区域，隶属于某栋楼，例如 A 栋-地下车库 B2 层。"""

    building = models.ForeignKey(
        Building, verbose_name='所属楼栋', related_name='areas', on_delete=models.PROTECT
    )
    code = models.CharField('区域编号', max_length=40)
    name = models.CharField('区域名称', max_length=80)
    location = models.CharField('位置描述', max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'org_area'
        unique_together = ('building', 'code')
        ordering = ['building__code', 'code']

    def __str__(self):
        return f'{self.building.name}/{self.name}'
