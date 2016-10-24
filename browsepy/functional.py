

NOT_DEFINED = type('NotDefinedType', (object,), {})


def psetattr(obj, name, value=NOT_DEFINED):
    '''
    Sets given value to given object, in a deferred way. Thought as a setattr
    partial which returns value instead of None.

    This function also works as decorator.

    :param obj: object which attr will be set
    :type obj: object
    :param name: attribute name will be set
    :type name: str
    :param value: attribute value will be set on `obj` with name `name`
    :type value: any

    :return: value given as `value` param
    :rtype: any
    '''
    def wrapped(value):
        setattr(obj, name, value)
        return value
    return wrapped if value is NOT_DEFINED else wrapped(value)
