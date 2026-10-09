"""Optional HTTP backend. Importing this package does not start a server or worker."""


def create_app(*args, **kwargs):
    from kami.service.app import create_app as factory
    return factory(*args, **kwargs)
