class Validate:
    @staticmethod
    def is_numeric(value, min=None, max=None) -> bool:
        try:
            value = int(str(value))
        except (TypeError, ValueError):
            return False
        if min is not None and value < min:
            return False
        elif max is not None and value > max:
            return False
        return True
