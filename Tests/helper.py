import importlib


def get_class_instance(class_name, class_path):
    module = importlib.import_module(class_path)
    class_name = getattr(module, class_name)
    class_instance = class_name()
    return class_instance
