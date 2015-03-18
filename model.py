from peewee import Model, CharField, DateTimeField, TextField, IntegerField, CharField
from playhouse import db_url

db = db_url.connect("sqlite:///default.db")


class BaseModel(Model):

    @classmethod
    def get_default(cls, **kwargs):
        try:
            return cls.get(**kwargs)
        except cls.DoesNotExit:
            pass

    def to_dict(self):
        return self._data

    class Meta:
        database = db

class Task(Model):

    create_time = DateTimeField()
    finish_time = DateTimeField(null=True)
    username = CharField()
    password = CharField()
    mail = CharField()
    parse_result = TextField(null=True)
    status = IntegerField(default=0)  # 0-queued 1-finished 2-failed

db.create_tables([Task], safe=True)
