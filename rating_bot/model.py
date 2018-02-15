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

    def __str__(self):
        return '%d, место %s' % (self.value, format_float(self.position))

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


def format_float(x):
    return ('%f' % x).rstrip('0').rstrip('.')


def rating_diff(old, new):
    if old is None or old == new:
        return str(new)

    vdiff = new.value - old.value
    vsign = '+' if vdiff >= 0 else ''
    vdiff_str = '%s%d' % (vsign, vdiff)

    pdiff = new.position - old.position
    psign = '+' if pdiff >= 0 else ''
    pdiff_str = '%s%s' % (psign, format_float(pdiff))

    return '%d (%s), место %s (%s)' % (new.value, vdiff_str, format_float(new.position), pdiff_str)
