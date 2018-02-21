class Team:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    def __str__(self):
        return '%s (#%d)' % (self.name, self.id)


class Rating:
    def __init__(self, value, position, value_diff=None, position_diff=None):
        self.value = value or 0
        self.position = position or 0
        self.value_diff = value_diff
        self.position_diff = position_diff

    def __str__(self):
        value_str = str(self.value)
        if self.value_diff:
            sign = '+' if self.value_diff > 0 else ''
            value_str += ' (%s%d)' % (sign, self.value_diff)

        position_str = format_float(self.position)
        if self.position_diff:
            sign = '+' if self.position_diff > 0 else ''
            position_str += ' (%s%s)' % (sign, format_float(self.position_diff))
        return '%s, место %s' % (value_str, position_str)

    def __eq__(self, other):
        if not isinstance(other, Rating):
            return False
        return (self.value, self.position) == (other.value, other.position)

    def __sub__(self, other):
        return Rating(self.value,
                      self.position,
                      self.value - other.value,
                      other.position - self.position)

    @classmethod
    def fromJSON(self, json):
        return Rating(int(json['rating']), float(json['rating_position']))


def format_float(x):
    return ('%f' % x).rstrip('0').rstrip('.')
