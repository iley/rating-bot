class Team:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    def __str__(self):
        return '%s (#%d)' % (self.name, self.id)


class RatingRecord:
    def __init__(self, release, value, position):
        self.release = release
        self.value = value
        self.position = position

    def __eq__(self, other):
        if not isinstance(other, RatingRecord):
            return False
        return (self.release, self.value, self.position) == \
            (other.release, other.value, other.position)

    @classmethod
    def fromJSON(self, json):
        return RatingRecord(int(json['idrelease']),
                            int(json['rating']),
                            float(json['rating_position']))
